"""
J.A.R.V.I.S. Instagram DM Automation — Real-Time MQTT Engine
=============================================================
Uses instagrapi's built-in MQTT/Realtime client (edge-mqtt.facebook.com) for
**instant**, event-driven DM handling — no polling lag.

Architecture
------------
  1. On enable(), authenticate the instagrapi Client and call
     realtime_connect() + direct_subscribe() to register for the
     Instagram IRIS DM sync stream.
  2. Register a "message" event handler; every time Instagram pushes a
     new DM event the handler fires *immediately* (sub-second).
  3. The handler checks if the incoming item is from a friend (not from
     Sir), reconstructs the thread transcript, generates a Gemini reply,
     and sends it back — all within seconds.
  4. A lightweight keep-alive loop pings the MQTT connection every 25 s
     and reconnects automatically if it drops.
  5. On disable(), the MQTT connection is cleanly disconnected.
  6. Falls back to fast polling (every 20 s) if MQTT connection fails.

This module is a singleton — get_dm_automator() returns the global instance.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Awaitable, Optional, Set

logger = logging.getLogger("jarvis.instagram_dm_automation")

# ---------------------------------------------------------------------------
# Sentinel strings from auto_reply_instagram_dms() that mean "nothing to do"
# ---------------------------------------------------------------------------
_NO_REPLY_PHRASES = ("up-to-date", "no pending", "no unanswered", "offline")


class InstagramDMAutomator:
    """
    Real-time Instagram DM automation daemon.

    Usage
    -----
        automator = get_dm_automator()
        task = asyncio.create_task(automator.run_loop(broadcast_fn))
        # enable/disable at runtime:
        automator.enable()
        automator.disable()
    """

    # Ping interval (seconds) — Instagram drops idle MQTT after ~60 s
    PING_INTERVAL = 25
    # Fallback polling interval when MQTT is unavailable
    POLL_INTERVAL_FALLBACK = 20

    def __init__(self):
        self.enabled: bool = False
        self.running: bool = False

        # Runtime state
        self._broadcast: Optional[Callable[[dict], Awaitable[None]]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._replied_ids: Set[str] = set()   # de-duplicate by message item_id
        self._last_ping: float = 0.0
        self._mqtt_active: bool = False
        self._cl = None                        # cached instagrapi Client

        # Telemetry
        self.total_replied: int = 0
        self.last_scan: Optional[str] = None
        self.last_replies: list = []
        self.mode: str = "idle"               # "mqtt" | "poll" | "idle"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enable(self, poll_interval: int = None):
        """Enable the daemon. MQTT is attempted first; fallback to polling."""
        self.enabled = True
        logger.info("Instagram DM Automation: ENABLED")

    def disable(self):
        """Pause the daemon and disconnect MQTT cleanly."""
        self.enabled = False
        self._disconnect_mqtt()
        self.mode = "idle"
        logger.info("Instagram DM Automation: DISABLED")

    def get_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "running": self.running,
            "mode": self.mode,
            "mqtt_active": self._mqtt_active,
            "last_scan": self.last_scan,
            "total_replied": self.total_replied,
            "last_replies": self.last_replies[-5:],
        }

    # ------------------------------------------------------------------
    # Main daemon loop (run as asyncio background task)
    # ------------------------------------------------------------------

    async def run_loop(self, broadcast_fn: Callable[[dict], Awaitable[None]]):
        self._broadcast = broadcast_fn
        try:
            self._loop = asyncio.get_running_loop()
        except Exception:
            self._loop = asyncio.get_event_loop()
        self.running = True
        logger.info("Instagram DM Automation daemon started.")

        while self.running:
            if not self.enabled:
                self._disconnect_mqtt()
                self.mode = "idle"
                await asyncio.sleep(2)
                continue

            # Attempt / maintain MQTT connection
            if not self._mqtt_active:
                connected = await asyncio.to_thread(self._connect_mqtt)
                if connected:
                    if self.mode != "mqtt":
                        self.mode = "mqtt"
                        await self._emit_log("📲 Instagram DM Automation: MQTT real-time stream CONNECTED.")
                else:
                    if self.mode != "poll":
                        self.mode = "poll"
                        await self._emit_log("📲 Instagram DM Automation: Running in background polling mode.")

            if self._mqtt_active:
                # Drain any pending MQTT packets (non-blocking)
                await asyncio.to_thread(self._drain_mqtt_packets)
                # Periodic keep-alive ping
                if time.monotonic() - self._last_ping > self.PING_INTERVAL:
                    alive = await asyncio.to_thread(self._mqtt_ping)
                    if not alive:
                        logger.warning("MQTT ping failed — reconnecting.")
                        self._mqtt_active = False
                        self._disconnect_mqtt()
                await asyncio.sleep(1)
            else:
                # Polling fallback
                await self._poll_and_reply()
                await asyncio.sleep(self.POLL_INTERVAL_FALLBACK)

        self._disconnect_mqtt()
        logger.info("Instagram DM Automation daemon stopped.")

    # ------------------------------------------------------------------
    # MQTT helpers (all blocking — run in thread pool via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _get_client(self):
        """Return the cached instagrapi Client, initialising it if needed."""
        if self._cl is None:
            from core.instagram import get_instagram_client
            self._cl = get_instagram_client()
        return self._cl

    def _connect_mqtt(self) -> bool:
        """Connect to Instagram's real-time MQTT stream. Returns True on success."""
        try:
            cl = self._get_client()
            if cl is None:
                return False

            # Subscribe to the IRIS DM stream — fetches seq_id + snapshot_at_ms
            cl.realtime_connect()
            cl.realtime.on("message", self._on_mqtt_message)
            cl.realtime.direct_subscribe(amount=1)
            self._mqtt_active = True
            self._last_ping = time.monotonic()
            logger.info("Instagram MQTT real-time stream connected.")
            return True
        except Exception as e:
            logger.warning(f"Instagram MQTT connect failed: {e}")
            self._mqtt_active = False
            return False

    def _disconnect_mqtt(self):
        """Cleanly disconnect MQTT if active."""
        try:
            if self._cl and self._mqtt_active:
                self._cl.realtime_disconnect()
        except Exception:
            pass
        self._mqtt_active = False

    def _drain_mqtt_packets(self, max_packets: int = 10):
        """
        Read up to max_packets from the MQTT socket in one pass.
        Each packet dispatches the registered "message" handler synchronously.
        """
        if not self._cl or not self._mqtt_active:
            return
        try:
            # Set a short socket timeout so we don't block the event loop
            transport = self._cl.realtime.transport
            if hasattr(transport, "_sock") and transport._sock:
                transport._sock.settimeout(0.5)
            for _ in range(max_packets):
                try:
                    self._cl.realtime_read_once()
                except OSError:
                    # Timeout — no data waiting, that's fine
                    break
        except Exception as e:
            logger.debug(f"MQTT drain error: {e}")
            self._mqtt_active = False

    def _mqtt_ping(self) -> bool:
        """Send a keep-alive PING. Returns True if PONG received."""
        try:
            if self._cl and self._mqtt_active:
                result = self._cl.realtime_ping()
                self._last_ping = time.monotonic()
                return result
        except Exception as e:
            logger.debug(f"MQTT ping error: {e}")
        return False

    def _on_mqtt_message(self, event: Any):
        """
        Called synchronously by instagrapi when a DM-related MQTT message
        arrives. We check if it's an inbound message from a friend and reply.
        """
        if not self.enabled:
            return
        try:
            msg = event.get("message", {}) if isinstance(event, dict) else {}
            thread_id = msg.get("thread_id") or event.get("thread_id") if isinstance(event, dict) else None
            item = msg.get("item") or {}
            item_id = item.get("item_id") or msg.get("item_id")
            sender_id = str(item.get("user_id") or msg.get("user_id") or "")
            item_type = item.get("item_type") or msg.get("item_type") or "text"
            text = item.get("text") or msg.get("text") or ""

            cl = self._get_client()
            if not cl or not thread_id:
                return

            # Skip if this message is from Sir himself
            if sender_id and sender_id == str(cl.user_id):
                return

            # Deduplicate — don't reply to the same message twice
            if item_id and item_id in self._replied_ids:
                return
            if item_id:
                self._replied_ids.add(item_id)
                # Keep set bounded
                if len(self._replied_ids) > 1000:
                    self._replied_ids = set(list(self._replied_ids)[-500:])

            # Fetch thread to build transcript and get friend username
            self._reply_to_thread(thread_id, cl)

        except Exception as e:
            logger.error(f"MQTT message handler error: {e}")

    def _reply_to_thread(self, thread_id: str, cl):
        """Fetch the thread, generate a reply, and send it."""
        try:
            from core.instagram import format_thread_transcript, generate_ai_friend_reply
            thread = cl.direct_thread(thread_id, amount=10)
            if not thread or not thread.users:
                return

            # Only handle 1-on-1 or small group chats (≤3 participants)
            if len(thread.users) > 3:
                return

            # Last message must be from a friend, not Sir
            if not thread.messages:
                return
            last = thread.messages[0]
            if str(getattr(last, "user_id", "")) == str(cl.user_id):
                return

            friend_user = thread.users[0]
            friend_username = friend_user.username

            transcript = format_thread_transcript(thread, cl.user_id)
            reply_text = generate_ai_friend_reply(friend_username, transcript)

            # Send reply via REST API (reliable delivery)
            cl.direct_answer(thread_id, reply_text)

            # Log to SQLite cortex
            try:
                from core.database import log_social_dm
                last_text = getattr(last, "text", "") or "[Media]"
                log_social_dm(
                    platform="instagram",
                    sender=friend_username,
                    recipient=cl.username,
                    message_text=last_text,
                    thread_id=str(thread_id),
                    is_incoming=True,
                    ai_response=reply_text,
                    status="replied",
                    raw_payload={"transcript": transcript},
                )
            except Exception:
                pass

            entry = f"@{friend_username}: \"{reply_text}\""
            self.total_replied += 1
            self.last_replies.append(entry)
            self.last_scan = datetime.now().strftime("%H:%M:%S")
            logger.info(f"Instagram DM replied → {entry}")

            # Quiet diagnostic log broadcast to HUD (never spamming chat or speaking aloud)
            if self._broadcast and self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._broadcast({
                        "log": f"📲 Instagram DM sent → @{friend_username}: \"{reply_text[:60]}{'…' if len(reply_text) > 60 else ''}\"",
                        "friend": friend_username,
                    }),
                    self._loop,
                )
        except Exception as e:
            logger.error(f"_reply_to_thread error (thread {thread_id}): {e}")

    # ------------------------------------------------------------------
    # Polling fallback (used when MQTT is unavailable)
    # ------------------------------------------------------------------

    async def _poll_and_reply(self):
        """Fast polling fallback — scans inbox and replies to pending messages quietly."""
        try:
            replies = await asyncio.to_thread(self._blocking_poll)
            self.last_scan = datetime.now().strftime("%H:%M:%S")
            if replies:
                self.total_replied += len(replies)
                self.last_replies.extend(replies)
                self.last_replies = self.last_replies[-20:]
                if self._broadcast:
                    await self._broadcast({
                        "log": f"📲 Instagram DM: Dispatched {len(replies)} autonomous reply(ies) — {self.last_scan}",
                        "detail": "\n".join(replies),
                    })
        except Exception as e:
            logger.error(f"Instagram poll error: {e}")
            await self._emit_log(f"⚠️ Instagram DM poll error: {e}")

    def _blocking_poll(self) -> list:
        """Synchronous fast-poll using instagrapi REST API with deduplication."""
        from core.instagram import auto_reply_instagram_dms
        results = auto_reply_instagram_dms()
        sent = [r for r in results if r and not any(p in r.lower() for p in _NO_REPLY_PHRASES)]
        return sent

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _emit_log(self, text: str):
        if self._broadcast:
            await self._broadcast({"log": text})


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_instance: Optional[InstagramDMAutomator] = None


def get_dm_automator() -> InstagramDMAutomator:
    global _instance
    if _instance is None:
        _instance = InstagramDMAutomator()
    return _instance

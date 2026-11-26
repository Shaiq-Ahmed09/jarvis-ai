import asyncio
import json
import websockets

async def verify():
    uri = "ws://127.0.0.1:8765/ws"
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        print("Connected successfully!")
        
        received_types = set()
        replies = []
        
        # Send a conversational prompt
        await ws.send(json.dumps({"type": "task", "text": "Jarvis, status report. Are all neural systems operational?"}))
        print("Sent task: 'Jarvis, status report. Are all neural systems operational?'")

        for _ in range(30):
            try:
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg_raw)
                mtype = data.get("type")
                received_types.add(mtype)
                
                if mtype in ["say_text", "say_stream_text"]:
                    text = data.get("text", "")
                    replies.append(text)
                    print(f"[{mtype}] {text}")
                elif mtype in ["biometric_telemetry", "predictive_workflows", "ar_window_matrix"]:
                    print(f"[{mtype}] received: keys={list(data.keys())}")
                elif mtype == "say_stream_end":
                    print("[say_stream_end] Stream finished!")
                    break
            except asyncio.TimeoutError:
                print("Wait timeout.")
                break

        print("\n=== VERIFICATION SUMMARY ===")
        print("Received Message Types:", sorted(list(received_types)))
        print("Total Replies:", len(replies))
        full_reply = " ".join(replies)
        print("Full Assistant Reply:", full_reply)
        assert len(replies) > 0, "No reply received from J.A.R.V.I.S.!"
        print("VERIFICATION SUCCESSFUL: AI is fully responsive and communicating!")

asyncio.run(verify())

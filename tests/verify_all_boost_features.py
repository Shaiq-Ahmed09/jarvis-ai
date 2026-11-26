import asyncio
import json
import websockets

async def verify_all():
    uri = "ws://127.0.0.1:8765/ws"
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        print("Connected successfully!")
        
        # 1. Test Quantum P2P Mesh
        print("\n--- 1. Testing Quantum P2P Mesh ---")
        await ws.send(json.dumps({
            "type": "send_p2p_packet",
            "peer_id": "NODE-MARK-VII-SATELLITE",
            "message": "Orbital telemetry handshake verified."
        }))
        await ws.send(json.dumps({
            "type": "pair_p2p_node",
            "node_name": "Orbital Relay Epsilon"
        }))

        # 2. Test Code Self-Patch Diagnostics
        print("\n--- 2. Testing Autonomous Code Self-Patch Diagnostics ---")
        await ws.send(json.dumps({"type": "get_code_diagnostics"}))

        # 3. Test Voice Clone Biometric Studio
        print("\n--- 3. Testing Voice Clone Biometric Studio ---")
        await ws.send(json.dumps({"type": "get_voice_profiles"}))
        await ws.send(json.dumps({"type": "audition_voice_profile", "profile_id": "friday_aux"}))
        await ws.send(json.dumps({"type": "set_voice_profile", "profile_id": "jarvis_prime"}))

        # 4. Test LLM Tool Execution for new capabilities
        print("\n--- 4. Testing End-to-End Autonomous Directive ---")
        await ws.send(json.dumps({
            "type": "task",
            "text": "Jarvis, check the quantum P2P mesh status and run code self-diagnostics."
        }))

        received_types = set()
        p2p_status = None
        code_diag = None
        voice_data = None
        audition_received = False
        llm_replies = []

        for _ in range(35):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=6.0)
                data = json.loads(raw)
                mtype = data.get("type")
                received_types.add(mtype)

                if mtype == "p2p_mesh_status":
                    p2p_status = data
                    print(f"  [P2P MESH] Active Peers: {data.get('active_peers_count')} | Cipher: {data.get('cipher_suite')} | TX: {len(data.get('recent_transmissions', []))}")
                elif mtype == "code_diagnostics":
                    code_diag = data
                    print(f"  [CODE DIAG] Health Score: {data.get('health_score')}% | Modules Checked: {data.get('checked_modules')} | LOC: {data.get('total_lines_of_code')}")
                elif mtype == "voice_profiles_data":
                    voice_data = data
                    print(f"  [VOICE PROFILES] Active: {data.get('active_id')} | Total Profiles: {len(data.get('profiles', []))}")
                elif mtype == "voice_audition_clip":
                    audition_received = True
                    print(f"  [VOICE AUDITION] Synthesized clip for '{data.get('profile_id')}': phrase=\"{data.get('phrase')}\" ({len(data.get('audio', ''))} b64 chars)")
                elif mtype in ["say_text", "say_stream_text"]:
                    text = data.get("text", "")
                    llm_replies.append(text)
                    print(f"  [JARVIS REPLY] {text}")
                elif mtype == "say_stream_end":
                    print("  [STREAM END]")
                    break
            except asyncio.TimeoutError:
                print("Wait timeout.")
                break

        print("\n================== VERIFICATION SUMMARY ==================")
        print("Message Types Received:", sorted(list(received_types)))
        assert p2p_status is not None, "Failed to receive p2p_mesh_status!"
        assert code_diag is not None, "Failed to receive code_diagnostics!"
        assert voice_data is not None, "Failed to receive voice_profiles_data!"
        assert audition_received, "Failed to receive voice audition clip!"
        assert len(llm_replies) > 0, "Failed to receive LLM reply!"

        print("\nALL VERIFICATION CRITERIA MET WITH 100% SUCCESS:")
        print(f"  1. Quantum P2P: {p2p_status['cipher_suite']} with {p2p_status['active_peers_count']} peers")
        print(f"  2. Code Self-Patcher: {code_diag['health_score']}% health across {code_diag['checked_modules']} modules")
        print(f"  3. Voice Clone Studio: {len(voice_data['profiles'])} biometric profiles active, audition verified")
        print(f"  4. J.A.R.V.I.S. Directive: {' '.join(llm_replies)}")

asyncio.run(verify_all())

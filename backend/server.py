import asyncio
import websockets
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8765))

waiting_player = None
active_games = {}
player_games = {}

async def handle_client(websocket):
    global waiting_player
    import json
    logger.info(f"Connected! Port={PORT}")
    try:
        async for message in websocket:
            data = json.loads(message)
            t = data.get("type")
            if t == "find_game":
                if waiting_player is None or waiting_player == websocket:
                    waiting_player = websocket
                    await websocket.send(json.dumps({"type":"waiting"}))
                else:
                    opp = waiting_player
                    waiting_player = None
                    gid = f"{id(opp)}-{id(websocket)}"
                    active_games[gid] = {"white":opp,"black":websocket}
                    player_games[id(opp)] = gid
                    player_games[id(websocket)] = gid
                    await opp.send(json.dumps({"type":"game_start","color":"w"}))
                    await websocket.send(json.dumps({"type":"game_start","color":"b"}))
                    logger.info("Game started!")
            elif t == "move":
                gid = player_games.get(id(websocket))
                game = active_games.get(gid)
                if game:
                    opp = game["black"] if websocket==game["white"] else game["white"]
                    await opp.send(json.dumps({"type":"move","fr":data["fr"],"fc":data["fc"],"tr":data["tr"],"tc":data["tc"],"promotion":data.get("promotion","--")}))
            elif t == "resign":
                gid = player_games.get(id(websocket))
                game = active_games.get(gid)
                if game:
                    opp = game["black"] if websocket==game["white"] else game["white"]
                    await opp.send(json.dumps({"type":"opponent_resigned"}))
    except:
        pass
    finally:
        if waiting_player == websocket:
            waiting_player = None
        gid = player_games.pop(id(websocket), None)
        if gid:
            game = active_games.pop(gid, None)
            if game:
                opp = game["black"] if websocket==game["white"] else game["white"]
                player_games.pop(id(opp), None)
                try:
                    await opp.send(json.dumps({"type":"opponent_disconnected"}))
                except:
                    pass

async def main():
    logger.info(f"Server starting on 0.0.0.0:{PORT}")
    async with websockets.serve(
        handle_client,
        "0.0.0.0",
        PORT,
        ping_interval=20,
        ping_timeout=60
    ) as server:
        logger.info(f"Server ready on port {PORT}!")
        await server.serve_forever()

asyncio.run(main())

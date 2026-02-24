import asyncio
import websockets
import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8765))

waiting_player = None
active_games = {}
player_games = {}


async def handle_client(websocket):
    global waiting_player
    logger.info("New connection")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "find_game":
                if waiting_player is None or waiting_player == websocket:
                    waiting_player = websocket
                    await websocket.send(json.dumps({"type": "waiting"}))
                    logger.info("Player waiting...")
                else:
                    opponent = waiting_player
                    waiting_player = None
                    game_id = f"{id(opponent)}-{id(websocket)}"
                    active_games[game_id] = {"white": opponent, "black": websocket}
                    player_games[id(opponent)] = game_id
                    player_games[id(websocket)] = game_id
                    await opponent.send(json.dumps({"type": "game_start", "color": "w"}))
                    await websocket.send(json.dumps({"type": "game_start", "color": "b"}))
                    logger.info(f"Game started: {game_id}")

            elif msg_type == "move":
                game_id = player_games.get(id(websocket))
                if not game_id:
                    continue
                game = active_games.get(game_id)
                if not game:
                    continue
                opponent = game["black"] if websocket == game["white"] else game["white"]
                try:
                    await opponent.send(json.dumps({
                        "type": "move",
                        "fr": data["fr"], "fc": data["fc"],
                        "tr": data["tr"], "tc": data["tc"],
                        "promotion": data.get("promotion", "--")
                    }))
                except Exception as e:
                    logger.error(f"Error forwarding move: {e}")

            elif msg_type == "resign":
                game_id = player_games.get(id(websocket))
                if not game_id:
                    continue
                game = active_games.get(game_id)
                if game:
                    opponent = game["black"] if websocket == game["white"] else game["white"]
                    try:
                        await opponent.send(json.dumps({"type": "opponent_resigned"}))
                    except:
                        pass

    except websockets.exceptions.ConnectionClosed:
        logger.info("Connection closed")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if waiting_player == websocket:
            waiting_player = None
        game_id = player_games.pop(id(websocket), None)
        if game_id:
            game = active_games.pop(game_id, None)
            if game:
                opponent = game["black"] if websocket == game["white"] else game["white"]
                player_games.pop(id(opponent), None)
                try:
                    await opponent.send(json.dumps({"type": "opponent_disconnected"}))
                except:
                    pass


async def main():
    logger.info(f"Chess server starting on port {PORT}")
    async with websockets.serve(handle_client, "0.0.0.0", PORT):
        logger.info(f"Server running on port {PORT}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

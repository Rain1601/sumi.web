import { createRoom } from "./api";

export async function connectToAgent(agentId: string, userToken: string) {
  const room = await createRoom(agentId, userToken);
  console.log("[LiveKit] connecting to:", room.livekit_url, "room:", room.room_name);
  return {
    serverUrl: room.livekit_url,
    token: room.token,
    roomName: room.room_name,
  };
}

import { createRoom } from "./api";

export async function connectToAgent(agentId: string, userToken: string) {
  const room = await createRoom(agentId, userToken);
  return {
    serverUrl: room.livekit_url,
    token: room.token,
    roomName: room.room_name,
  };
}

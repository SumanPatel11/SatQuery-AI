import api from "./api";

export async function sendChatQuery({
  query,
  imageId = null,
  sessionId = null,
  context = {},
}) {
  if (!query?.trim()) {
    throw new Error("Query cannot be empty.");
  }

  return api.sendQuery({
    query: query.trim(),
    imageId,
    sessionId,
    context,
  });
}

export async function checkChatService() {
  return api.getHealth();
}

export default {
  sendChatQuery,
  checkChatService,
};
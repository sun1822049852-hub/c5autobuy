import { serializeItemPayload } from "./query_system_models.js";


export async function persistQueryConfigDraft({
  client,
  sourceConfig,
  draftConfig,
}) {
  const draftItemIds = new Set((draftConfig.items || []).map((item) => item.query_item_id));

  for (const item of sourceConfig?.items || []) {
    if (!draftItemIds.has(item.query_item_id)) {
      await client.deleteQueryItem(draftConfig.config_id, item.query_item_id);
    }
  }

  for (const item of draftConfig.items || []) {
    if (item.isNew) {
      await client.addQueryItem(
        draftConfig.config_id,
        serializeItemPayload(item, { includeProductUrl: true }),
      );
      continue;
    }

    await client.updateQueryItem(
      draftConfig.config_id,
      item.query_item_id,
      serializeItemPayload(item),
    );
  }
}

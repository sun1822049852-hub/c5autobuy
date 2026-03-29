import { serializeItemPayload } from "./query_system_models.js";


function areSerializedItemsEqual(leftItem, rightItem) {
  return JSON.stringify(serializeItemPayload(leftItem)) === JSON.stringify(serializeItemPayload(rightItem));
}


export async function persistQueryConfigDraft({
  client,
  sourceConfig,
  draftConfig,
}) {
  const sourceItemsById = new Map((sourceConfig?.items || []).map((item) => [item.query_item_id, item]));
  const draftItemIds = new Set((draftConfig.items || []).map((item) => item.query_item_id));
  const persistedQueryItemIds = [];
  let deletedAnyItem = false;

  for (const item of sourceConfig?.items || []) {
    if (!draftItemIds.has(item.query_item_id)) {
      await client.deleteQueryItem(draftConfig.config_id, item.query_item_id);
      deletedAnyItem = true;
    }
  }

  for (const item of draftConfig.items || []) {
    if (item.isNew) {
      const createdItem = await client.addQueryItem(
        draftConfig.config_id,
        serializeItemPayload(item, { includeProductUrl: true }),
      );
      persistedQueryItemIds.push(String(createdItem?.query_item_id || item.query_item_id));
      continue;
    }

    const sourceItem = sourceItemsById.get(item.query_item_id);
    if (sourceItem && areSerializedItemsEqual(sourceItem, item)) {
      continue;
    }

    const updatedItem = await client.updateQueryItem(
      draftConfig.config_id,
      item.query_item_id,
      serializeItemPayload(item),
    );
    persistedQueryItemIds.push(String(updatedItem?.query_item_id || item.query_item_id));
  }

  return {
    deletedAnyItem,
    persistedQueryItemIds,
  };
}

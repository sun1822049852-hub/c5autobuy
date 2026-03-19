const memoryStore = new Map();


function resolveStorage() {
  try {
    return globalThis.window?.localStorage ?? null;
  } catch {
    return null;
  }
}


export function createUiStateStore(key) {
  const storage = resolveStorage();

  return {
    read(defaultValue) {
      const rawValue = storage ? storage.getItem(key) : memoryStore.get(key);

      if (!rawValue) {
        return defaultValue;
      }

      try {
        return JSON.parse(rawValue);
      } catch {
        return defaultValue;
      }
    },
    write(value) {
      const serialized = JSON.stringify(value);

      if (storage) {
        storage.setItem(key, serialized);
        return;
      }

      memoryStore.set(key, serialized);
    },
  };
}

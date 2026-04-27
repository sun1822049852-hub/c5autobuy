function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

function nowIso(now = new Date()) {
  return now instanceof Date ? now.toISOString() : new Date(now).toISOString();
}

function createRuntimeControlHub({
  now = () => new Date(),
  keepaliveMs = 30000,
  streamVersion = "runtime-control/v1"
} = {}) {
  const subscribers = new Map();
  const keepaliveDelayMs = Math.max(100, Number(keepaliveMs) || 30000);
  let nextSubscriberId = 1;

  function removeSubscriber(subscriberId) {
    for (const [userId, userSubscribers] of subscribers.entries()) {
      if (!userSubscribers.has(subscriberId)) {
        continue;
      }
      const subscriber = userSubscribers.get(subscriberId);
      userSubscribers.delete(subscriberId);
      if (!userSubscribers.size) {
        subscribers.delete(userId);
      }
      if (subscriber && subscriber.keepaliveTimer) {
        clearInterval(subscriber.keepaliveTimer);
      }
      return;
    }
  }

  function writeFrame(subscriber, frame) {
    if (!subscriber || !subscriber.res || subscriber.res.destroyed || subscriber.closed) {
      removeSubscriber(subscriber && subscriber.id);
      return false;
    }
    try {
      subscriber.res.write(frame);
      return true;
    } catch {
      removeSubscriber(subscriber.id);
      return false;
    }
  }

  function sendEvent(subscriber, eventName, payload) {
    return writeFrame(
      subscriber,
      `event: ${toText(eventName)}\ndata: ${JSON.stringify(payload)}\n\n`
    );
  }

  function sendKeepalive(subscriber) {
    return writeFrame(subscriber, `: keepalive ${nowIso(now())}\n\n`);
  }

  function subscribe({
    userId = 0,
    deviceId = "",
    req = null,
    res = null
  } = {}) {
    const numericUserId = Number(userId) || 0;
    const normalizedDeviceId = toText(deviceId);
    const subscriberId = nextSubscriberId++;
    const subscriber = {
      id: subscriberId,
      userId: numericUserId,
      deviceId: normalizedDeviceId,
      req,
      res,
      keepaliveTimer: null,
      closed: false
    };

    if (!subscribers.has(numericUserId)) {
      subscribers.set(numericUserId, new Map());
    }
    subscribers.get(numericUserId).set(subscriberId, subscriber);

    const cleanup = () => {
      if (subscriber.keepaliveTimer) {
        clearInterval(subscriber.keepaliveTimer);
        subscriber.keepaliveTimer = null;
      }
      if (subscriber.closed) {
        return;
      }
      subscriber.closed = true;
      removeSubscriber(subscriberId);
    };

    if (req && typeof req.on === "function") {
      req.on("close", cleanup);
      req.on("aborted", cleanup);
      req.on("error", cleanup);
    }
    if (res && typeof res.on === "function") {
      res.on("close", cleanup);
      res.on("error", cleanup);
    }

    const helloDelivered = sendEvent(subscriber, "hello", {
      server_time: nowIso(now()),
      stream_version: streamVersion,
      user_id: numericUserId,
      device_id: normalizedDeviceId
    });
    if (!helloDelivered) {
      cleanup();
      return {
        close: cleanup,
        sendRuntimeRevoke() {
          return false;
        }
      };
    }
    subscriber.keepaliveTimer = setInterval(() => {
      sendKeepalive(subscriber);
    }, keepaliveDelayMs);

    return {
      close: cleanup,
      sendRuntimeRevoke({
        reason = "",
        nowValue = now()
      } = {}) {
        return sendEvent(subscriber, "runtime.revoke", {
          reason: toText(reason) || "runtime_permission_revoked",
          server_time: nowIso(nowValue)
        });
      }
    };
  }

  function broadcastRuntimeRevoke({
    userId = 0,
    reason = "",
    nowValue = now()
  } = {}) {
    const userSubscribers = subscribers.get(Number(userId) || 0);
    if (!userSubscribers || !userSubscribers.size) {
      return {deliveredCount: 0};
    }
    let deliveredCount = 0;
    for (const subscriber of userSubscribers.values()) {
      const delivered = sendEvent(subscriber, "runtime.revoke", {
        reason: toText(reason) || "runtime_permission_revoked",
        server_time: nowIso(nowValue)
      });
      if (delivered) {
        deliveredCount += 1;
      }
    }
    return {deliveredCount};
  }

  function close() {
    const allSubscribers = [];
    for (const userSubscribers of subscribers.values()) {
      for (const subscriber of userSubscribers.values()) {
        allSubscribers.push(subscriber);
      }
    }
    subscribers.clear();
    for (const subscriber of allSubscribers) {
      subscriber.closed = true;
      if (subscriber.keepaliveTimer) {
        clearInterval(subscriber.keepaliveTimer);
      }
      try {
        if (subscriber.res && !subscriber.res.destroyed) {
          subscriber.res.end();
        }
      } catch {
        // ignore close failures on shutdown
      }
    }
  }

  return {
    subscribe,
    broadcastRuntimeRevoke,
    close
  };
}

module.exports = {
  createRuntimeControlHub
};

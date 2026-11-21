/**
 * ALORA Offline Queue (IndexedDB)
 * Persists recorded audio blobs locally when mobile networks drop in the field,
 * and replays them automatically once connectivity returns.
 */
(function (global) {
  const DB_NAME = "alora_offline_queue_db";
  const DB_VERSION = 1;
  const STORE_NAME = "pending_recordings";

  function openDb() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in global)) {
        reject(new Error("IndexedDB non supporté par ce navigateur"));
        return;
      }
      const req = global.indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "id", autoIncrement: true });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function addPending(item) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const req = store.add({
        ...item,
        savedAt: new Date().toISOString(),
      });
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function listPending() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readonly");
      const store = tx.objectStore(STORE_NAME);
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  }

  async function removePending(id) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const req = store.delete(id);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  }

  global.AloraOfflineQueue = {
    addPending,
    listPending,
    removePending,
  };
})(window);

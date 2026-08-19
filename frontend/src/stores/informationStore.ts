import { api } from "../api/client";

export interface ArticleItem {
  title: string;
  url: string;
  published_at: string | null;
  summary: string;
  image_url: string | null;
  category: string;
}

interface InformationStore {
  xyxw: ArticleItem[];
  xshuhd: ArticleItem[];
  xshenghd: ArticleItem[];
  tzgg: ArticleItem[];
  loaded: boolean;
  loading: boolean;
  error: boolean;
}

const store: InformationStore = {
  xyxw: [],
  xshuhd: [],
  xshenghd: [],
  tzgg: [],
  loaded: false,
  loading: false,
  error: false,
};

const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((fn) => fn());
}

export async function preloadInformationData() {
  if (store.loaded || store.loading) return;
  store.loading = true;
  notify();

  try {
    const data = await api.getExternal<{
      xyxw: ArticleItem[];
      xshuhd: ArticleItem[];
      xshenghd: ArticleItem[];
      tzgg: ArticleItem[];
    }>("/api/information/home");

    store.xyxw = (data as any).xyxw ?? [];
    store.xshuhd = (data as any).xshuhd ?? [];
    store.xshenghd = (data as any).xshenghd ?? [];
    store.tzgg = (data as any).tzgg ?? [];
    store.loaded = true;
    store.error = false;
  } catch {
    store.error = true;
  } finally {
    store.loading = false;
    notify();
  }
}

export function getInformationStore(): Readonly<InformationStore> {
  return store;
}

export function subscribeToInformationStore(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
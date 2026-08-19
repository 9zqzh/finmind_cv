import { api } from "../api/client";

export interface CompetitionItem {
  id: string;
  title: string;
  url: string;
  category: string;
  year: number | null;
  recognition: string;
  status: string;
  department: string;
  registration_mode: string;
  max_team_size: number | null;
  max_advisors: number | null;
  registration_start_at: string | null;
  registration_end_at: string | null;
  event_start_at: string | null;
  event_end_at: string | null;
  official_url: string | null;
  wechat_article_url: string | null;
  cta_type: string;
  cta_label: string | null;
  summary: string;
}

export interface NoticeItem {
  id: string;
  title: string;
  content: string;
  priority: string;
  published_at: string;
  competition_title: string | null;
  competition_id: string | null;
}

export interface ClubItem {
  slug: string;
  name: string;
  short_name: string;
  slogan: string;
  cover_image: string | null;
  theme_color: string | null;
  focus_areas: string[];
  url: string;
}

interface CompetitionStore {
  items: CompetitionItem[];
  notices: NoticeItem[];
  clubs: ClubItem[];
  loaded: boolean;
  loading: boolean;
  error: boolean;
}

const store: CompetitionStore = {
  items: [],
  notices: [],
  clubs: [],
  loaded: false,
  loading: false,
  error: false,
};

const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((fn) => fn());
}

function mapCompetition(item: Record<string, unknown>): CompetitionItem {
  return {
    id: String(item.id ?? ""),
    title: String(item.title ?? ""),
    url: `https://ai-data-competitions.cn/competitions/${item.id}`,
    category: String(item.category ?? ""),
    year: (item.competitionYear as number) ?? null,
    recognition: String(item.recognition ?? ""),
    status: String(item.status ?? ""),
    department: String(item.department ?? ""),
    registration_mode: String(item.registrationMode ?? ""),
    max_team_size: (item.maxTeamSize as number) ?? null,
    max_advisors: (item.maxAdvisors as number) ?? null,
    registration_start_at: (item.registrationStartAt as string) ?? null,
    registration_end_at: (item.registrationEndAt as string) ?? null,
    event_start_at: (item.eventStartAt as string) ?? null,
    event_end_at: (item.eventEndAt as string) ?? null,
    official_url: (item.officialUrl as string) ?? null,
    wechat_article_url: (item.wechatArticleUrl as string) ?? null,
    cta_type: String(item.ctaType ?? ""),
    cta_label: (item.ctaLabelOverride as string) ?? null,
    summary: String(item.summary ?? ""),
  };
}

function mapNotice(item: Record<string, unknown>): NoticeItem {
  return {
    id: String(item.id ?? ""),
    title: String(item.title ?? ""),
    content: String(item.content ?? ""),
    priority: String(item.priority ?? "normal"),
    published_at: (item.publishedAt as string) ?? "",
    competition_title: (item.competitionTitle as string) ?? null,
    competition_id: (item.competitionId as string) ?? null,
  };
}

function mapClub(item: Record<string, unknown>): ClubItem {
  const slug = String(item.slug ?? "");
  return {
    slug,
    name: String(item.name ?? ""),
    short_name: String(item.shortName ?? ""),
    slogan: String(item.slogan ?? ""),
    cover_image: (item.coverImage as string) ?? null,
    theme_color: (item.themeColor as string) ?? null,
    focus_areas: (item.focusAreas as string[]) ?? [],
    url: `https://ai-data-competitions.cn/clubs/${slug}`,
  };
}

export async function preloadCompetitionData() {
  if (store.loaded || store.loading) return;
  store.loading = true;
  notify();

  try {
    const [compRes, noticeRes, clubRes] = await Promise.all([
      api.getExternal<{ competitions: Record<string, unknown>[] }>(
        "/api/competitions/list"
      ),
      api.getExternal<{ notices: Record<string, unknown>[] }>(
        "/api/competitions/notices"
      ),
      api.getExternal<{ data: Record<string, unknown>[] }>(
        "/api/competitions/clubs"
      ),
    ]);

    store.items = (compRes as any).competitions?.map(mapCompetition) ?? [];
    store.notices = (noticeRes as any).notices?.map(mapNotice) ?? [];
    store.clubs = (clubRes as any).data?.map(mapClub) ?? [];
    store.loaded = true;
    store.error = false;
  } catch {
    store.error = true;
  } finally {
    store.loading = false;
    notify();
  }
}

export function getCompetitionStore(): Readonly<CompetitionStore> {
  return store;
}

export function subscribeToCompetitionStore(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
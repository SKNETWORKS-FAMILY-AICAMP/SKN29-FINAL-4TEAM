export interface PageInfo {
  page: number;
  size: number;
  total: number;
}

export interface PaginatedData<TItem> {
  items: TItem[];
  page_info: PageInfo;
}

export function getTotalPages(pageInfo: PageInfo): number {
  if (pageInfo.size < 1) return 1;
  return Math.max(1, Math.ceil(pageInfo.total / pageInfo.size));
}

export function normalizePageInfo(pageInfo: PageInfo): PageInfo {
  return {
    page: Math.max(1, Math.trunc(pageInfo.page)),
    size: Math.min(100, Math.max(1, Math.trunc(pageInfo.size))),
    total: Math.max(0, Math.trunc(pageInfo.total)),
  };
}

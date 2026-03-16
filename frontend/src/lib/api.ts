const BASE_URL = "https://api.marketwire.ai";

// ─── helpers ────────────────────────────────────────
async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      body.message || `Request failed with status ${res.status}`,
      res.status
    );
  }

  return res.json();
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// ─── Auth ───────────────────────────────────────────
export interface RegisterPayload {
  email: string;
  password: string;
  phone?: string;
  account_type?: string;
}

export interface AuthResponse {
  message: string;
  user_id: string;
  token: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface UserProfile {
  UserID: string;
  emailID: string;
  Phone_Number: string | null;
  Paid: string;
  AccountType: string;
  created_at: string;
}

export async function register(payload: RegisterPayload): Promise<AuthResponse> {
  return request("/api/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function login(payload: LoginPayload): Promise<AuthResponse> {
  return request("/api/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout(token: string): Promise<{ message: string }> {
  return request("/api/logout", { method: "POST" }, token);
}

export async function getUser(token: string): Promise<UserProfile> {
  return request("/api/user", {}, token);
}

// ─── Corporate Filings ─────────────────────────────
export interface Filing {
  corp_id: string;
  securityid: string;
  summary: string;
  fileurl: string | null;
  date: string;
  ai_summary: string | null;
  category: string;
  isin: string;
  companyname: string;
  symbol: string;
  headline: string | null;
  sentiment: string | null;
  is_read?: boolean;
  investorCorp?: InvestorInfo[];
}

export interface InvestorInfo {
  id: string;
  investor_id: string;
  investor_name: string;
  aliasBool: boolean | string;
  aliasName: string | null;
  verified: boolean | string;
  type: string;
  alias_id: string | null;
}

export interface FilingsResponse {
  count: number;
  current_page: number;
  filings: Filing[];
  has_next: boolean;
  has_previous: boolean;
  page_size: number;
  total_count: number;
  total_pages: number;
}

export interface FilingsParams {
  start_date?: string;
  end_date?: string;
  category?: string;
  symbol?: string;
  isin?: string;
  watchlist?: boolean;
  read_filter?: "all" | "read" | "unread";
  marketcap?: string;
  include_duplicates?: boolean;
  page?: number;
  page_size?: number;
}

export async function getCorporateFilings(
  params: FilingsParams = {},
  token?: string | null
): Promise<FilingsResponse> {
  const qs = new URLSearchParams();
  if (params.start_date) qs.set("start_date", params.start_date);
  if (params.end_date) qs.set("end_date", params.end_date);
  if (params.category) qs.set("category", params.category);
  if (params.symbol) qs.set("symbol", params.symbol);
  if (params.isin) qs.set("isin", params.isin);
  if (params.watchlist) qs.set("watchlist", "true");
  if (params.read_filter && params.read_filter !== "all")
    qs.set("read_filter", params.read_filter);
  if (params.marketcap) qs.set("marketcap", params.marketcap);
  if (params.include_duplicates) qs.set("include_duplicates", "true");
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return request(`/api/v2/corporate_filings${q ? `?${q}` : ""}`, {}, token);
}

export async function getFilingById(
  corpId: string,
  token?: string | null
): Promise<Filing> {
  return request(`/api/v2/corporate_filings/${corpId}`, {}, token);
}

export async function markFilingsRead(
  token: string,
  corpIds: string[]
): Promise<{ message: string; count: number }> {
  return request(
    "/api/v2/corporate_filings/mark-read",
    { method: "POST", body: JSON.stringify({ corp_ids: corpIds }) },
    token
  );
}

export async function markFilingsUnread(
  token: string,
  corpIds: string[]
): Promise<{ message: string; count: number }> {
  return request(
    "/api/v2/corporate_filings/mark-unread",
    { method: "POST", body: JSON.stringify({ corp_ids: corpIds }) },
    token
  );
}

export async function getReadStatus(
  token: string,
  corpIds: string[]
): Promise<{ read_corp_ids: string[] }> {
  return request(
    "/api/v2/corporate_filings/read-status",
    { method: "POST", body: JSON.stringify({ corp_ids: corpIds }) },
    token
  );
}

// ─── Company Search ─────────────────────────────────
export interface Company {
  newname: string;
  oldname: string;
  newnsecode: string;
  oldnsecode: string;
  newbsecode: string;
  oldbsecode: string;
  isin: string;
}

export interface CompanySearchResponse {
  count: number;
  companies: Company[];
}

export async function searchCompanies(
  query: string,
  limit = 10
): Promise<CompanySearchResponse> {
  return request(
    `/api/company/search?q=${encodeURIComponent(query)}&limit=${limit}`
  );
}

// ─── Announcement Count ─────────────────────────────
export interface CountResponse {
  start_date: string;
  end_date: string;
  grand_total: number;
  total_counts: Record<string, number>;
}

export async function getAnnouncementCount(
  startDate: string,
  endDate: string
): Promise<CountResponse> {
  return request(
    `/api/get_count?start_date=${startDate}&end_date=${endDate}`
  );
}

// ─── Watchlists ─────────────────────────────────────
export interface Watchlist {
  _id: string;
  watchlistName: string;
  categories: string[];
  isin: string[];
}

export interface WatchlistsResponse {
  watchlists: Watchlist[];
}

export async function getWatchlists(
  token: string
): Promise<WatchlistsResponse> {
  return request("/api/watchlist", {}, token);
}

export async function createWatchlist(
  token: string,
  name: string,
  type: "DS" | "SM" | "NA" = "NA"
): Promise<{ message: string; watchlist_id: string }> {
  return request(
    "/api/watchlist",
    {
      method: "POST",
      body: JSON.stringify({
        operation: "create",
        watchlistName: name,
        watchlistType: type,
      }),
    },
    token
  );
}

export async function addIsinToWatchlist(
  token: string,
  watchlistId: string,
  isin: string,
  categories?: string[]
): Promise<{ message: string }> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const body: any = {
    operation: "add_isin",
    watchlist_id: watchlistId,
  };
  if (isin) body.isin = isin;
  if (categories && categories.length > 0) body.categories = categories;
  return request(
    "/api/watchlist",
    { method: "POST", body: JSON.stringify(body) },
    token
  );
}

export async function addCategoriesToWatchlist(
  token: string,
  watchlistId: string,
  categories: string[]
): Promise<{ message: string }> {
  return request(
    "/api/watchlist",
    {
      method: "POST",
      body: JSON.stringify({
        operation: "add_isin",
        watchlist_id: watchlistId,
        categories,
      }),
    },
    token
  );
}

export async function removeCategoryFromWatchlist(
  token: string,
  watchlistId: string,
  category: string
): Promise<{ message: string }> {
  return request(
    `/api/watchlist/${watchlistId}/category/${encodeURIComponent(category)}`,
    { method: "DELETE" },
    token
  );
}

export async function resolveIsins(
  isins: string[]
): Promise<Record<string, string>> {
  const mapping: Record<string, string> = {};
  const batch = isins.slice(0, 50); // limit to 50
  await Promise.all(
    batch.map(async (isin) => {
      try {
        const res = await searchCompanies(isin, 1);
        if (res.companies?.length > 0) {
          mapping[isin] = res.companies[0].newname;
        }
      } catch { /* skip */ }
    })
  );
  return mapping;
}

export async function removeIsinFromWatchlist(
  token: string,
  watchlistId: string,
  isin: string
): Promise<{ message: string }> {
  return request(
    `/api/watchlist/${watchlistId}/isin/${isin}`,
    { method: "DELETE" },
    token
  );
}

export async function deleteWatchlist(
  token: string,
  watchlistId: string
): Promise<{ message: string }> {
  return request(
    `/api/watchlist/${watchlistId}`,
    { method: "DELETE" },
    token
  );
}

// ─── Saved Announcements ────────────────────────────
export interface SavedItem {
  id: string;
  ai_summary: string | null;
  category: string;
  companyname: string;
  corp_id: string;
  date: string;
  fileurl: string | null;
  headline: string | null;
  investors: InvestorInfo[];
  isin: string;
  note: string;
  saved_at: string;
  securityid: string;
  sentiment: string | null;
  summary: string;
  symbol: string;
  user_id: string;
  // Price tracking fields (computed by backend)
  saved_price: number | null;
  current_price: number | null;
  percentage_change: number | null;
  absolute_change: number | null;
}

export async function saveAnnouncement(
  token: string,
  itemId: string,
  isin: string,
  itemType: "ANNOUNCEMENT" | "LARGE_DEALS" = "ANNOUNCEMENT",
  note = ""
): Promise<{ message: string; status: string }> {
  return request(
    "/api/save_announcement",
    {
      method: "POST",
      body: JSON.stringify({
        item_type: itemType,
        item_id: itemId,
        isin,
        note,
      }),
    },
    token
  );
}

export async function fetchSavedAnnouncements(
  token: string
): Promise<{ message: string; status: string; data: SavedItem[] }> {
  return request("/api/fetch_saved_announcements", {}, token);
}

export async function deleteSavedAnnouncement(
  token: string,
  savedItemId: string
): Promise<{ message: string }> {
  return request(
    `/api/delete_saved_announcement/${savedItemId}`,
    { method: "DELETE" },
    token
  );
}



export async function bulkAddIsins(
  token: string,
  watchlistId: string,
  isins: string[],
  categories?: string[]
): Promise<{ message: string }> {
  return request(
    "/api/watchlist/bulk_add",
    {
      method: "POST",
      body: JSON.stringify({
        watchlist_id: watchlistId,
        isins,
        categories,
      }),
    },
    token
  );
}

// ─── Financial Results ──────────────────────────────
export interface FinancialResult {
  id: string;
  corp_id: string;
  company_id: string;
  isin: string;
  period: string;
  sales_current: number | null;
  sales_previous_year: number | null;
  pat_current: number | null;
  pat_previous: number | null;
  sales_yoy: number | null;
  pat_yoy: number | null;
  fileurl: string | null;
  verified: string;
  verified_at: string | null;
  verified_by: string | null;
  corporatefilings?: {
    date: string;
    companyname: string;
    headline: string | null;
    category: string;
    ai_summary: string | null;
    symbol: string;
  };
}

export interface FinancialResultsResponse {
  count: number;
  total_count: number;
  total_pages: number;
  current_page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
  financial_results: FinancialResult[];
}

export interface FinancialResultsParams {
  start_date?: string;
  end_date?: string;
  symbol?: string;
  isin?: string;
  page?: number;
  page_size?: number;
}

export async function getFinancialResults(
  params: FinancialResultsParams = {}
): Promise<FinancialResultsResponse> {
  const qs = new URLSearchParams();
  if (params.start_date) qs.set("start_date", params.start_date);
  if (params.end_date) qs.set("end_date", params.end_date);
  if (params.symbol) qs.set("symbol", params.symbol);
  if (params.isin) qs.set("isin", params.isin);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return request(`/api/financial_results${q ? `?${q}` : ""}`);
}

// ─── Bulk & Block Deals ─────────────────────────────
export interface Deal {
  id: string;
  symbol: string;
  securityid: string;
  date: string;
  client_name: string;
  deal_type: string;
  quantity: number;
  price: string;
  exchange: string;
  deal: string;
  created_at: string;
}

export interface DealsResponse {
  success: boolean;
  deals: Deal[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface DealsParams {
  exchange?: string;
  deal?: string;
  deal_type?: string;
  start_date?: string;
  end_date?: string;
  symbol?: string;
  page?: number;
  page_size?: number;
}

export async function getDeals(
  token: string,
  params: DealsParams = {}
): Promise<DealsResponse> {
  const qs = new URLSearchParams();
  if (params.exchange) qs.set("exchange", params.exchange);
  if (params.deal) qs.set("deal", params.deal);
  if (params.deal_type) qs.set("deal_type", params.deal_type);
  if (params.start_date) qs.set("start_date", params.start_date);
  if (params.end_date) qs.set("end_date", params.end_date);
  if (params.symbol) qs.set("symbol", params.symbol);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return request(`/api/deals${q ? `?${q}` : ""}`, {}, token);
}

// ─── Corporate Actions ──────────────────────────────
export interface CorporateAction {
  id: number;
  sec_code: string;
  symbol: string;
  company_name: string;
  ex_date: string;
  purpose: string;
  record_date: string | null;
  bc_start_date: string | null;
  bc_end_date: string | null;
  nd_start_date: string | null;
  nd_end_date: string | null;
  payment_date: string | null;
  exchange: string;
  isin: string;
  series: string | null;
  face_value: string | null;
  action_required: boolean;
  created_at: string;
  updated_at: string;
}

export interface CorporateActionsResponse {
  success: boolean;
  data: CorporateAction[];
  pagination: {
    current_page: number;
    page_size: number;
    total_records: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  };
}

export interface CorporateActionsParams {
  exchange?: string;
  start_date?: string;
  end_date?: string;
  symbol?: string;
  page?: number;
  page_size?: number;
}

export async function getCorporateActions(
  token: string,
  params: CorporateActionsParams = {}
): Promise<CorporateActionsResponse> {
  const qs = new URLSearchParams();
  if (params.exchange) qs.set("exchange", params.exchange);
  if (params.start_date) qs.set("start_date", params.start_date);
  if (params.end_date) qs.set("end_date", params.end_date);
  if (params.symbol) qs.set("symbol", params.symbol);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return request(`/api/corporate_actions${q ? `?${q}` : ""}`, {}, token);
}

// ─── Insider Trading ────────────────────────────────
export interface InsiderTrade {
  insider_uuid: string;
  sec_code: string;
  sec_name: string;
  symbol: string;
  person_name: string;
  person_cat: string;
  pre_sec_type: string;
  pre_sec_num: number;
  pre_sec_pct: number;
  trans_sec_type: string;
  trans_sec_num: number;
  trans_value: number;
  trans_type: string;
  post_sec_type: string;
  post_sec_num: number;
  post_sec_pct: number;
  date_from: string;
  date_to: string;
  date_intimation: string;
  mode_acq: string;
  exchange: string;
  reported_to_exchange: string;
}

export interface InsiderTradingResponse {
  success: boolean;
  data: InsiderTrade[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface InsiderTradingParams {
  exchange?: string;
  start_date?: string;
  end_date?: string;
  symbol?: string;
  person_name?: string;
  page?: number;
  page_size?: number;
}

export async function getInsiderTrading(
  token: string,
  params: InsiderTradingParams = {}
): Promise<InsiderTradingResponse> {
  const qs = new URLSearchParams();
  if (params.exchange) qs.set("exchange", params.exchange);
  if (params.start_date) qs.set("start_date", params.start_date);
  if (params.end_date) qs.set("end_date", params.end_date);
  if (params.symbol) qs.set("symbol", params.symbol);
  if (params.person_name) qs.set("person_name", params.person_name);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return request(`/api/insider_trading${q ? `?${q}` : ""}`, {}, token);
}

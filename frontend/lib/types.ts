export type Role = "admin" | "viewer";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: Role;
  email: string;
}

export interface UnitTypeAggregate {
  unit_type: string;
  total_available: number;
  buildings_count: number;
  rent_min: number | null;
  rent_max: number | null;
  rent_avg: number | null;
  sqft_min: number | null;
  sqft_max: number | null;
}

export interface BuildingSummary {
  id: number;
  name: string;
  address: string;
  last_scraped_at: string | null;
  last_scrape_status: string;
  last_scrape_error: string | null;
  source_url: string | null;
  total_units: number;
  units_by_type: Record<string, number>;
  rent_min: number | null;
  rent_max: number | null;
  rent_avg: number | null;
  has_incentive: boolean;
  incentive_raw: string | null;
  incentive_parsed: Record<string, unknown> | null;
  incentive_source_url: string | null;
}

export interface UnitOut {
  id: number;
  unit_identifier: string;
  unit_type: string;
  rent: number;
  sqft: number | null;
  floor: number | null;
  available_date: string | null;
  listing_url: string | null;
  listing_type: string;
  is_currently_available: boolean;
  last_seen_at: string;
}

export interface BuildingDetail extends BuildingSummary {
  units: UnitOut[];
}

export interface DashboardResponse {
  generated_at: string;
  last_run_finished_at: string | null;
  total_units: number;
  total_buildings: number;
  buildings_succeeded: number;
  buildings_failed: number;
  buildings_with_incentives: number;
  by_unit_type: UnitTypeAggregate[];
  buildings: BuildingSummary[];
}

export interface ScrapeTriggerResponse {
  run_id: number;
  status: string;
  buildings_attempted: number;
  buildings_succeeded: number;
  total_units_found: number;
  started_at: string;
  finished_at: string | null;
  elapsed_seconds: number;
}

-- ==============================================================================
-- MVP 2.0 Supabase Database Schema: LandsatWater Precision Groundwater Siting
-- PostgreSQL 15+ with PostGIS, Row-Level Security (RLS), and Multi-Tenancy
-- ==============================================================================

-- 1. Enable PostGIS Extension
create extension if not exists postgis;

-- 2. Organisations (Tenancy Root)
create table if not exists public.organisations (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    slug text not null unique,
    tier text not null default 'COMMERCIAL_FREE' check (tier in ('COMMERCIAL_FREE', 'COMMERCIAL_PRO', 'ENTERPRISE')),
    created_at timestamptz not null default now()
);

-- 3. User Profiles (Linked to Supabase Auth)
create table if not exists public.user_profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    organisation_id uuid not null references public.organisations(id) on delete restrict,
    role text not null default 'HYD_ENGINEER' check (role in ('SUPER_ADMIN', 'ORG_ADMIN', 'HYD_ENGINEER', 'FIELD_OPERATOR', 'VIEWER')),
    full_name text not null default '',
    created_at timestamptz not null default now()
);

-- 4. Reference Boreholes (Read-only Public Ground Truth: BGI, ORASECOM, STAS)
create table if not exists public.reference_boreholes (
    id uuid primary key default gen_random_uuid(),
    source_id text not null,
    source_name text not null, -- 'BGI_BOTSWANA', 'ORASECOM', 'STAS_GGRETA'
    geom geometry(Point, 4326) not null,
    country text not null default 'BOTSWANA',
    aquifer text not null default 'Kalahari / Auob',
    yield_m3h numeric null,
    tds_mg_l numeric null,
    depth_m numeric null,
    is_strike boolean not null default true,
    created_at timestamptz not null default now()
);
create index if not exists idx_ref_boreholes_geom on public.reference_boreholes using gist(geom);

-- 5. Tenant Boreholes (Private Organization Assets & Imported Ground-Truth)
create table if not exists public.boreholes (
    id uuid primary key default gen_random_uuid(),
    organisation_id uuid not null references public.organisations(id) on delete cascade,
    name text not null,
    geom geometry(Point, 4326) not null,
    drilled_at date null,
    yield_m3h numeric null,
    tds_mg_l numeric null,
    depth_m numeric null,
    is_strike boolean not null default true,
    provenance text not null default 'FIELD_SURVEY', -- 'FIELD_SURVEY', 'CSV_IMPORT', 'DRILL_LOG'
    created_at timestamptz not null default now()
);
create index if not exists idx_boreholes_org on public.boreholes(organisation_id);
create index if not exists idx_boreholes_geom on public.boreholes using gist(geom);

-- 6. Model Versions (Metadata & Deployment Gate)
create table if not exists public.model_versions (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    model_type text not null, -- 'PU_FRACTURE_SCORER', 'STAGE1_STRIKE', 'STAGE2_YIELD'
    metrics jsonb not null default '{}'::jsonb,
    storage_path text not null,
    is_active boolean not null default false,
    created_at timestamptz not null default now()
);

-- 7. Analysis Runs (Asynchronous Siting Execution via Postgres Queue)
create table if not exists public.analysis_runs (
    id uuid primary key default gen_random_uuid(),
    organisation_id uuid not null references public.organisations(id) on delete cascade,
    created_by uuid references auth.users(id) on delete set null,
    status text not null default 'QUEUED' check (status in ('QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED')),
    centre geometry(Point, 4326) not null,
    boundary geometry(Polygon, 4326) null,
    radius_km numeric not null default 50.0,
    snap_m numeric not null default 50.0,
    yield_threshold_m3h numeric not null default 5.0,
    error_message text null,
    model_version text null,
    overall_strike_prob numeric null,
    overall_yield_tier text null,
    telemetry_summary jsonb null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_runs_org on public.analysis_runs(organisation_id);
create index if not exists idx_runs_status on public.analysis_runs(status);
create index if not exists idx_runs_centre on public.analysis_runs using gist(centre);

-- 8. Fractures (Structural Lineament Edge Vectors extracted via Earth Engine)
create table if not exists public.fractures (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references public.analysis_runs(id) on delete cascade,
    geom geometry(LineString, 4326) not null,
    length_m numeric not null,
    azimuth_deg numeric not null,
    confidence numeric not null,
    lineament_family text not null default 'NE-SW', -- 'NE-SW', 'NW-SE', 'E-W', 'N-S'
    created_at timestamptz not null default now()
);
create index if not exists idx_fractures_run on public.fractures(run_id);
create index if not exists idx_fractures_geom on public.fractures using gist(geom);

-- 9. Ranked Drill Targets & 200m ERT Lines
create table if not exists public.drill_targets (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references public.analysis_runs(id) on delete cascade,
    rank integer not null check (rank between 1 and 10),
    target_id text not null,
    geom geometry(Point, 4326) not null,
    strike_probability numeric not null check (strike_probability between 0.0 and 1.0),
    yield_tier text not null check (yield_tier in ('Commercial High (≥ 5.0 m³/h)', 'Moderate (1.0 - 5.0 m³/h)', 'Low / Domestic (< 1.0 m³/h)')),
    estimated_yield_m3h numeric not null,
    recommended_depth_m numeric not null,
    depth_to_water_strike_m numeric not null,
    estimated_tds_salinity_mg_l numeric not null,
    ert_line_geom geometry(LineString, 4326) not null,
    ert_strike_deg numeric not null,
    evidence_notes text not null default '',
    created_at timestamptz not null default now()
);
create index if not exists idx_targets_run on public.drill_targets(run_id);
create index if not exists idx_targets_geom on public.drill_targets using gist(geom);

-- ==============================================================================
-- Row-Level Security (RLS) Policies
-- Enforces absolute tenant isolation by organization
-- ==============================================================================

alter table public.organisations enable row level security;
alter table public.user_profiles enable row level security;
alter table public.boreholes enable row level security;
alter table public.analysis_runs enable row level security;
alter table public.fractures enable row level security;
alter table public.drill_targets enable row level security;
alter table public.reference_boreholes enable row level security;
alter table public.model_versions enable row level security;

-- Helper function to extract user's current organisation_id
create or replace function public.current_org_id()
returns uuid language sql stable as $$
  select organisation_id from public.user_profiles where id = auth.uid()
$$;

-- Reference boreholes: readable by any authenticated user
create policy "Authenticated users can read reference boreholes"
    on public.reference_boreholes for select
    to authenticated
    using (true);

-- Model versions: readable by any authenticated user
create policy "Authenticated users can read model versions"
    on public.model_versions for select
    to authenticated
    using (true);

-- Organisations: users can only see their own organisation
create policy "Users can view own organisation"
    on public.organisations for select
    to authenticated
    using (id = public.current_org_id());

-- User Profiles: users can read members of their own organisation
create policy "Users can view profiles in own organisation"
    on public.user_profiles for select
    to authenticated
    using (organisation_id = public.current_org_id());

-- Boreholes: tenant isolated CRUD
create policy "Tenant boreholes select"
    on public.boreholes for select
    to authenticated
    using (organisation_id = public.current_org_id());

create policy "Tenant boreholes insert"
    on public.boreholes for insert
    to authenticated
    with check (organisation_id = public.current_org_id());

create policy "Tenant boreholes update"
    on public.boreholes for update
    to authenticated
    using (organisation_id = public.current_org_id());

create policy "Tenant boreholes delete"
    on public.boreholes for delete
    to authenticated
    using (organisation_id = public.current_org_id());

-- Analysis Runs: tenant isolated
create policy "Tenant analysis_runs select"
    on public.analysis_runs for select
    to authenticated
    using (organisation_id = public.current_org_id());

create policy "Tenant analysis_runs insert"
    on public.analysis_runs for insert
    to authenticated
    with check (organisation_id = public.current_org_id());

create policy "Tenant analysis_runs update"
    on public.analysis_runs for update
    to authenticated
    using (organisation_id = public.current_org_id());

-- Fractures: viewable if the user owns the parent analysis run
create policy "Tenant fractures select"
    on public.fractures for select
    to authenticated
    using (
        exists (
            select 1 from public.analysis_runs r
            where r.id = fractures.run_id and r.organisation_id = public.current_org_id()
        )
    );

-- Drill Targets: viewable if the user owns the parent analysis run
create policy "Tenant drill_targets select"
    on public.drill_targets for select
    to authenticated
    using (
        exists (
            select 1 from public.analysis_runs r
            where r.id = drill_targets.run_id and r.organisation_id = public.current_org_id()
        )
    );

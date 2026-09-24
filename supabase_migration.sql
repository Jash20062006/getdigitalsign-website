-- Get Digital Sign — Blog CMS schema
-- Run this once in your Supabase project's SQL Editor (Project -> SQL Editor -> New query).

create table if not exists blogs (
  id bigint generated always as identity primary key,
  title text not null,
  slug text not null unique,
  excerpt text,
  content text not null,
  featured_image text,
  author text not null default 'Get Digital Sign Team',
  category text,
  meta_title text,
  meta_description text,
  keywords text,
  read_time text,
  status text not null default 'draft' check (status in ('draft', 'published')),
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists blogs_slug_idx on blogs (slug);
create index if not exists blogs_status_idx on blogs (status);
create index if not exists blogs_published_at_idx on blogs (published_at desc);

-- Keep updated_at current on every row update.
create or replace function set_blogs_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists blogs_set_updated_at on blogs;
create trigger blogs_set_updated_at
before update on blogs
for each row execute function set_blogs_updated_at();

-- Row Level Security: enabled with NO policies. The Flask backend talks to
-- Supabase using the service_role key, which bypasses RLS entirely, so the
-- app keeps working. This just guarantees that if the anon/public API key
-- ever leaked, it could not read or write this table directly.
alter table blogs enable row level security;

-- Public storage bucket for featured images / inline blog images.
-- Uploads only ever happen server-side (Flask, using the service_role key),
-- so making the bucket public-read is safe — it just means blog images can
-- be viewed by anyone, the same as any other image on the public site.
insert into storage.buckets (id, name, public)
values ('blog-images', 'blog-images', true)
on conflict (id) do nothing;

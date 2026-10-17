-- Replica of the pre-2.0 database as it existed on 2026-10-17 (column dump in
-- scripts/legacy/legacy_schema_2026-10-17.txt). Used by test_migrate_legacy.py.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY);
INSERT INTO alembic_version VALUES ('0c986b1c8a50');
CREATE TABLE brands (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, country varchar, website_url varchar,
                     logo_url varchar, description text, created_at timestamp DEFAULT now());
CREATE TABLE notes (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, category varchar, description text);
CREATE TABLE families (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, description text);
CREATE TABLE accords (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL);
CREATE TABLE occasions (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL);
CREATE TABLE retailers (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, website_url varchar, country varchar,
                        created_at timestamptz DEFAULT now());
CREATE TABLE fragrances (id serial PRIMARY KEY, brand_id integer REFERENCES brands(id), name varchar NOT NULL,
    concentration varchar, gender varchar, release_year integer, description text, longevity_hours numeric,
    sillage varchar, season_spring boolean, season_summer boolean, season_fall boolean, season_winter boolean,
    occasion_tags varchar[], available_sizes_ml integer[], image_url varchar, discontinued boolean,
    created_at timestamp DEFAULT now(), has_embedding boolean);
CREATE TABLE fragrance_accords (fragrance_id integer, accord_id integer);
CREATE TABLE fragrance_embeddings (fragrance_id integer PRIMARY KEY, embedding vector(384), text_input text,
                                   model_version varchar, generated_at timestamptz DEFAULT now());
CREATE TABLE fragrance_families (fragrance_id integer, family_id integer);
CREATE TABLE fragrance_families_map (fragrance_id integer, family_id integer);
CREATE TABLE fragrance_notes (fragrance_id integer, note_id integer, position varchar, prominence integer);
CREATE TABLE fragrance_occasions (fragrance_id integer, occasion_id integer);
CREATE TABLE fragrance_prices (id serial PRIMARY KEY, fragrance_id integer, size_ml integer, price_usd double precision);
CREATE TABLE price_entries (id serial PRIMARY KEY, fragrance_id integer, retailer_id integer, price_usd numeric,
                            spotted_at timestamp);
CREATE TABLE price_logs (id serial PRIMARY KEY, fragrance_id integer, retailer_id integer, size_ml integer,
                         price_usd double precision, product_url varchar, is_sale boolean, logged_at timestamptz DEFAULT now());
CREATE TABLE users (id uuid PRIMARY KEY, email varchar UNIQUE, password_hash varchar, display_name varchar,
                    role varchar, created_at timestamp DEFAULT now());
CREATE TABLE user_collection (id serial PRIMARY KEY, user_id uuid, fragrance_id integer, size_ml integer,
                              purchase_price numeric, rating numeric, remaining_pct integer, status varchar,
                              created_at timestamp DEFAULT now());

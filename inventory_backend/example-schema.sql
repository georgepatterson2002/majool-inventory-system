-- PostgreSQL schema dump (sanitized for public sharing)

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;

-- Example: brands table
CREATE TABLE public.brands (
    brand_id integer NOT NULL,
    brand_name text NOT NULL
);

CREATE SEQUENCE public.brands_brand_id_seq
    START WITH 1
    INCREMENT BY 1;

ALTER TABLE ONLY public.brands
    ALTER COLUMN brand_id SET DEFAULT nextval('public.brands_brand_id_seq');

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT brands_pkey PRIMARY KEY (brand_id);

-- Example: categories table
CREATE TABLE public.categories (
    category_id integer NOT NULL,
    name text NOT NULL
);

CREATE SEQUENCE public.categories_category_id_seq
    START WITH 1
    INCREMENT BY 1;

ALTER TABLE ONLY public.categories
    ALTER COLUMN category_id SET DEFAULT nextval('public.categories_category_id_seq');

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (category_id);

-- Example: products table
CREATE TABLE public.products (
    product_id integer NOT NULL,
    master_sku_id text NOT NULL,
    part_number text NOT NULL,
    product_name text NOT NULL,
    category_id integer NOT NULL,
    brand integer NOT NULL
);

CREATE SEQUENCE public.products_product_id_seq
    START WITH 1
    INCREMENT BY 1;

ALTER TABLE ONLY public.products
    ALTER COLUMN product_id SET DEFAULT nextval('public.products_product_id_seq');

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (product_id);

-- Example: users table (no sensitive fields exposed)
CREATE TABLE public.users (
    user_id integer NOT NULL,
    username text NOT NULL,
    password_hash text NOT NULL,
    is_admin boolean DEFAULT false
);

CREATE SEQUENCE public.users_user_id_seq
    START WITH 1
    INCREMENT BY 1;

ALTER TABLE ONLY public.users
    ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq');

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);

-- Inventory Units
CREATE TABLE public.inventory_units (
    unit_id integer NOT NULL,
    product_id integer NOT NULL,
    serial_number text NOT NULL,
    serial_assigned_at timestamp DEFAULT now(),
    assigned_by_user_id integer,
    po_number text DEFAULT 'UNKNOWN' NOT NULL,
    sn_prefix character varying(2),
    sold boolean DEFAULT false
);

-- Relationships (example only)
ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);

ALTER TABLE ONLY public.inventory_units
    ADD CONSTRAINT inventory_units_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(product_id);

-- Views (renamed for anonymity)
CREATE VIEW public.public_view_name_1 AS
SELECT product_id, part_number, product_name
FROM public.products;

CREATE VIEW public.public_view_name_2 AS
SELECT serial_number, po_number
FROM public.inventory_units;

-- Sample GRANT statements (safe, generic)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO staff_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO staff_role;

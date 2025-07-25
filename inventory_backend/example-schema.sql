-- PostgreSQL schema dump (sanitized for public sharing)

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;

-- Brands table
CREATE TABLE public.brands (
    brand_id integer NOT NULL,
    brand_name text NOT NULL
);

CREATE SEQUENCE public.brands_brand_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.brands ALTER COLUMN brand_id SET DEFAULT nextval('public.brands_brand_id_seq');
ALTER TABLE ONLY public.brands ADD CONSTRAINT brands_pkey PRIMARY KEY (brand_id);

-- Categories table
CREATE TABLE public.categories (
    category_id integer NOT NULL,
    name text NOT NULL
);

CREATE SEQUENCE public.categories_category_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.categories ALTER COLUMN category_id SET DEFAULT nextval('public.categories_category_id_seq');
ALTER TABLE ONLY public.categories ADD CONSTRAINT categories_pkey PRIMARY KEY (category_id);

-- Master SKUs table
CREATE TABLE public.master_skus (
    master_sku_id text NOT NULL,
    description text NOT NULL,
    created_at timestamp DEFAULT now(),
    CONSTRAINT master_skus_pkey PRIMARY KEY (master_sku_id)
);

-- Products table
CREATE TABLE public.products (
    product_id integer NOT NULL,
    master_sku_id text NOT NULL,
    part_number text NOT NULL,
    product_name text NOT NULL,
    category_id integer NOT NULL,
    brand integer NOT NULL,
    ssd_id integer
);

CREATE SEQUENCE public.products_product_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.products ALTER COLUMN product_id SET DEFAULT nextval('public.products_product_id_seq');
ALTER TABLE ONLY public.products ADD CONSTRAINT products_pkey PRIMARY KEY (product_id);

-- Users table (no sensitive fields exposed)
CREATE TABLE public.users (
    user_id integer NOT NULL,
    username text NOT NULL,
    password_hash text NOT NULL,
    is_admin boolean DEFAULT false
);

CREATE SEQUENCE public.users_user_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq');
ALTER TABLE ONLY public.users ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);

-- Inventory Units
CREATE TABLE public.inventory_units (
    unit_id integer NOT NULL,
    product_id integer NOT NULL,
    serial_number text NOT NULL,
    serial_assigned_at timestamp DEFAULT now(),
    assigned_by_user_id integer,
    po_number text DEFAULT 'UNKNOWN' NOT NULL,
    sn_prefix character varying(2),
    sold boolean DEFAULT false,
    is_damaged boolean DEFAULT false
);

CREATE SEQUENCE public.inventory_units_unit_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.inventory_units ALTER COLUMN unit_id SET DEFAULT nextval('public.inventory_units_unit_id_seq');
ALTER TABLE ONLY public.inventory_units ADD CONSTRAINT inventory_units_pkey PRIMARY KEY (unit_id);

-- Inventory Log
CREATE TABLE public.inventory_log (
    log_id integer NOT NULL,
    sku text NOT NULL,
    serial_number text,
    order_id text,
    event_time timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE public.inventory_log_log_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.inventory_log ALTER COLUMN log_id SET DEFAULT nextval('public.inventory_log_log_id_seq');
ALTER TABLE ONLY public.inventory_log ADD CONSTRAINT inventory_log_pkey PRIMARY KEY (log_id);

-- Manual Review
CREATE TABLE public.manual_review (
    review_id integer NOT NULL,
    order_id text NOT NULL,
    sku text NOT NULL,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    resolved boolean DEFAULT false,
    resolved_by_user_id integer
);

CREATE SEQUENCE public.manual_review_review_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.manual_review ALTER COLUMN review_id SET DEFAULT nextval('public.manual_review_review_id_seq');
ALTER TABLE ONLY public.manual_review ADD CONSTRAINT manual_review_pkey PRIMARY KEY (review_id);

-- Returns
CREATE TABLE public.returns (
    return_id integer NOT NULL,
    original_unit_id integer,
    product_id integer,
    serial_number text,
    serial_assigned_at timestamp,
    assigned_by_user_id integer,
    po_number text,
    sn_prefix character varying(2),
    sold boolean,
    return_date timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE public.returns_return_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.returns ALTER COLUMN return_id SET DEFAULT nextval('public.returns_return_id_seq');
ALTER TABLE ONLY public.returns ADD CONSTRAINT returns_pkey PRIMARY KEY (return_id);

-- Repairs
CREATE TABLE public.repairs (
    repair_id integer NOT NULL,
    unit_id integer NOT NULL,
    old_product_id integer NOT NULL,
    new_product_id integer,
    repaired_at timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE public.repairs_repair_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.repairs ALTER COLUMN repair_id SET DEFAULT nextval('public.repairs_repair_id_seq');
ALTER TABLE ONLY public.repairs ADD CONSTRAINT repairs_pkey PRIMARY KEY (repair_id);

-- Disposals
CREATE TABLE public.disposals (
    disposal_id integer NOT NULL,
    unit_id integer NOT NULL,
    original_product_id integer NOT NULL,
    disposed_at timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE public.disposals_disposal_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.disposals ALTER COLUMN disposal_id SET DEFAULT nextval('public.disposals_disposal_id_seq');
ALTER TABLE ONLY public.disposals ADD CONSTRAINT disposals_pkey PRIMARY KEY (disposal_id);

-- Reconciled Items
CREATE TABLE public.reconciled_items (
    reconciled_id integer NOT NULL,
    product_id integer NOT NULL,
    serial_number text,
    memo_number text,
    reconciled_at timestamp DEFAULT CURRENT_TIMESTAMP,
    resolved boolean DEFAULT false
);

CREATE SEQUENCE public.reconciled_items_reconciled_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.reconciled_items ALTER COLUMN reconciled_id SET DEFAULT nextval('public.reconciled_items_reconciled_id_seq');
ALTER TABLE ONLY public.reconciled_items ADD CONSTRAINT reconciled_items_pkey PRIMARY KEY (reconciled_id);

-- Untracked Serial Sales
CREATE TABLE public.untracked_serial_sales (
    id integer NOT NULL,
    product_id integer NOT NULL,
    order_id text NOT NULL,
    quantity integer NOT NULL,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE SEQUENCE public.untracked_serial_sales_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.untracked_serial_sales ALTER COLUMN id SET DEFAULT nextval('public.untracked_serial_sales_id_seq');
ALTER TABLE ONLY public.untracked_serial_sales ADD CONSTRAINT untracked_serial_sales_pkey PRIMARY KEY (id);

-- SSDs table
CREATE TABLE public.ssds (
    ssd_id integer NOT NULL,
    label text NOT NULL
);

CREATE SEQUENCE public.ssds_ssd_id_seq START WITH 1 INCREMENT BY 1;
ALTER TABLE ONLY public.ssds ALTER COLUMN ssd_id SET DEFAULT nextval('public.ssds_ssd_id_seq');
ALTER TABLE ONLY public.ssds ADD CONSTRAINT ssds_pkey PRIMARY KEY (ssd_id);

-- Relationships (sanitized)
ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_brand_fkey FOREIGN KEY (brand) REFERENCES public.brands(brand_id);

ALTER TABLE ONLY public.inventory_units
    ADD CONSTRAINT inventory_units_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(product_id);

ALTER TABLE ONLY public.reconciled_items
    ADD CONSTRAINT reconciled_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(product_id);

-- Example Views (safe, generic)
CREATE VIEW public.view_product_summary AS
SELECT product_id, part_number, product_name
FROM public.products;

CREATE VIEW public.view_serial_summary AS
SELECT serial_number, po_number
FROM public.inventory_units;

-- Sample GRANT statements (safe)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO staff_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO staff_role;

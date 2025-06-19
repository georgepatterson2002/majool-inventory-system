--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5

-- Started on 2025-06-19 15:23:47

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 235 (class 1259 OID 16614)
-- Name: brands; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.brands (
    brand_id integer NOT NULL,
    brand_name text NOT NULL
);


ALTER TABLE public.brands OWNER TO postgres;

--
-- TOC entry 234 (class 1259 OID 16613)
-- Name: brands_brand_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.brands_brand_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.brands_brand_id_seq OWNER TO postgres;

--
-- TOC entry 5023 (class 0 OID 0)
-- Dependencies: 234
-- Name: brands_brand_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.brands_brand_id_seq OWNED BY public.brands.brand_id;


--
-- TOC entry 221 (class 1259 OID 16501)
-- Name: categories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.categories (
    category_id integer NOT NULL,
    name text NOT NULL
);


ALTER TABLE public.categories OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 16506)
-- Name: categories_category_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.categories_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.categories_category_id_seq OWNER TO postgres;

--
-- TOC entry 5025 (class 0 OID 0)
-- Dependencies: 222
-- Name: categories_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.categories_category_id_seq OWNED BY public.categories.category_id;


--
-- TOC entry 223 (class 1259 OID 16507)
-- Name: inventory_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.inventory_log (
    log_id integer NOT NULL,
    sku text NOT NULL,
    serial_number text,
    order_id text,
    event_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.inventory_log OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 16513)
-- Name: inventory_log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.inventory_log_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_log_log_id_seq OWNER TO postgres;

--
-- TOC entry 5028 (class 0 OID 0)
-- Dependencies: 224
-- Name: inventory_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.inventory_log_log_id_seq OWNED BY public.inventory_log.log_id;


--
-- TOC entry 225 (class 1259 OID 16514)
-- Name: inventory_units; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.inventory_units (
    unit_id integer NOT NULL,
    product_id integer NOT NULL,
    serial_number text NOT NULL,
    serial_assigned_at timestamp without time zone DEFAULT now(),
    assigned_by_user_id integer,
    po_number text DEFAULT 'UNKNOWN'::text NOT NULL,
    sn_prefix character varying(2),
    sold boolean DEFAULT false
);


ALTER TABLE public.inventory_units OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 16520)
-- Name: inventory_units_unit_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.inventory_units_unit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_units_unit_id_seq OWNER TO postgres;

--
-- TOC entry 5032 (class 0 OID 0)
-- Dependencies: 226
-- Name: inventory_units_unit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.inventory_units_unit_id_seq OWNED BY public.inventory_units.unit_id;


--
-- TOC entry 227 (class 1259 OID 16521)
-- Name: manual_review; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.manual_review (
    review_id integer NOT NULL,
    order_id text NOT NULL,
    sku text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    resolved boolean DEFAULT false NOT NULL,
    resolved_by_user_id integer
);


ALTER TABLE public.manual_review OWNER TO postgres;

--
-- TOC entry 240 (class 1259 OID 16760)
-- Name: manual_review_log_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.manual_review_log_view AS
 SELECT il.log_id,
    il.sku,
    il.serial_number,
    il.order_id,
    il.event_time,
    iu.product_id,
    iu.sold,
        CASE
            WHEN (iu.serial_number IS NULL) THEN 'NOT FOUND'::text
            ELSE 'FOUND'::text
        END AS match_status
   FROM (public.inventory_log il
     LEFT JOIN public.inventory_units iu ON ((il.serial_number = iu.serial_number)))
  ORDER BY il.event_time DESC;


ALTER VIEW public.manual_review_log_view OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 16527)
-- Name: manual_review_review_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.manual_review_review_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.manual_review_review_id_seq OWNER TO postgres;

--
-- TOC entry 5036 (class 0 OID 0)
-- Dependencies: 228
-- Name: manual_review_review_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.manual_review_review_id_seq OWNED BY public.manual_review.review_id;


--
-- TOC entry 229 (class 1259 OID 16528)
-- Name: master_skus; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.master_skus (
    master_sku_id text NOT NULL,
    description text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT no_whitespace_msku CHECK ((master_sku_id = TRIM(BOTH FROM master_sku_id)))
);


ALTER TABLE public.master_skus OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 16535)
-- Name: products; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.products (
    product_id integer NOT NULL,
    master_sku_id text NOT NULL,
    part_number text NOT NULL,
    product_name text NOT NULL,
    category_id integer NOT NULL,
    brand integer NOT NULL
);


ALTER TABLE public.products OWNER TO postgres;

--
-- TOC entry 237 (class 1259 OID 16706)
-- Name: msku_product_summary; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.msku_product_summary AS
 WITH summary AS (
         SELECT p.master_sku_id,
            ( SELECT
                        CASE
                            WHEN (POSITION(('-'::text) IN (p2.part_number)) > 0) THEN "left"(p2.part_number, (POSITION(('-'::text) IN (p2.part_number)) - 1))
                            ELSE p2.part_number
                        END AS part_number
                   FROM public.products p2
                  WHERE (p2.master_sku_id = p.master_sku_id)
                  ORDER BY (length(p2.part_number)),
                        CASE
                            WHEN (POSITION(('-'::text) IN (p2.part_number)) > 0) THEN "left"(p2.part_number, (POSITION(('-'::text) IN (p2.part_number)) - 1))
                            ELSE p2.part_number
                        END
                 LIMIT 1) AS shortest_part_number,
            ( SELECT count(*) AS count
                   FROM (public.inventory_units iu
                     JOIN public.products p3 ON ((iu.product_id = p3.product_id)))
                  WHERE ((p3.master_sku_id = p.master_sku_id) AND (iu.sold = false))) AS total_inventory_count,
            ms.description AS msku_description
           FROM (public.products p
             JOIN public.master_skus ms ON ((p.master_sku_id = ms.master_sku_id)))
          WHERE (p.master_sku_id IS NOT NULL)
          GROUP BY p.master_sku_id, ms.master_sku_id, ms.description
        )
 SELECT master_sku_id,
    shortest_part_number,
    total_inventory_count,
    msku_description
   FROM summary
  ORDER BY shortest_part_number;


ALTER VIEW public.msku_product_summary OWNER TO postgres;

--
-- TOC entry 231 (class 1259 OID 16540)
-- Name: products_product_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.products_product_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.products_product_id_seq OWNER TO postgres;

--
-- TOC entry 5041 (class 0 OID 0)
-- Dependencies: 231
-- Name: products_product_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.products_product_id_seq OWNED BY public.products.product_id;


--
-- TOC entry 242 (class 1259 OID 16780)
-- Name: returns; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.returns (
    return_id integer NOT NULL,
    original_unit_id integer,
    product_id integer,
    serial_number text,
    serial_assigned_at timestamp without time zone,
    assigned_by_user_id integer,
    po_number text,
    sn_prefix character varying(2),
    sold boolean,
    return_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.returns OWNER TO postgres;

--
-- TOC entry 241 (class 1259 OID 16779)
-- Name: returns_return_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.returns_return_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.returns_return_id_seq OWNER TO postgres;

--
-- TOC entry 5044 (class 0 OID 0)
-- Dependencies: 241
-- Name: returns_return_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.returns_return_id_seq OWNED BY public.returns.return_id;


--
-- TOC entry 239 (class 1259 OID 16751)
-- Name: temp_rose_view; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.temp_rose_view AS
 SELECT
        CASE
            WHEN (POSITION(('-'::text) IN (p.part_number)) > 0) THEN "left"(p.part_number, (POSITION(('-'::text) IN (p.part_number)) - 1))
            ELSE p.part_number
        END AS part_number_prefix,
    min(p.product_name) AS sample_description,
    count(iu.unit_id) AS total_quantity
   FROM (public.products p
     LEFT JOIN public.inventory_units iu ON (((p.product_id = iu.product_id) AND (iu.sold = false))))
  GROUP BY
        CASE
            WHEN (POSITION(('-'::text) IN (p.part_number)) > 0) THEN "left"(p.part_number, (POSITION(('-'::text) IN (p.part_number)) - 1))
            ELSE p.part_number
        END
  ORDER BY
        CASE
            WHEN (POSITION(('-'::text) IN (p.part_number)) > 0) THEN "left"(p.part_number, (POSITION(('-'::text) IN (p.part_number)) - 1))
            ELSE p.part_number
        END;


ALTER VIEW public.temp_rose_view OWNER TO postgres;

--
-- TOC entry 232 (class 1259 OID 16541)
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    username text NOT NULL,
    password_hash text NOT NULL,
    is_admin boolean DEFAULT false
);


ALTER TABLE public.users OWNER TO postgres;

--
-- TOC entry 233 (class 1259 OID 16547)
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_user_id_seq OWNER TO postgres;

--
-- TOC entry 5048 (class 0 OID 0)
-- Dependencies: 233
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- TOC entry 236 (class 1259 OID 16674)
-- Name: view_product_details_readable; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.view_product_details_readable AS
 SELECT p.product_id,
    p.master_sku_id,
    p.part_number,
    p.product_name,
    c.name AS category,
    b.brand_name AS brand
   FROM ((public.products p
     JOIN public.categories c ON ((p.category_id = c.category_id)))
     JOIN public.brands b ON ((p.brand = b.brand_id)));


ALTER VIEW public.view_product_details_readable OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 16746)
-- Name: view_serials_with_part_numbers; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.view_serials_with_part_numbers AS
 SELECT iu.serial_number,
    p.part_number,
    iu.po_number,
    iu.serial_assigned_at AS scanned_at
   FROM (public.inventory_units iu
     JOIN public.products p ON ((iu.product_id = p.product_id)))
  ORDER BY iu.serial_assigned_at DESC;


ALTER VIEW public.view_serials_with_part_numbers OWNER TO postgres;

--
-- TOC entry 4820 (class 2604 OID 16617)
-- Name: brands brand_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.brands ALTER COLUMN brand_id SET DEFAULT nextval('public.brands_brand_id_seq'::regclass);


--
-- TOC entry 4806 (class 2604 OID 16558)
-- Name: categories category_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories ALTER COLUMN category_id SET DEFAULT nextval('public.categories_category_id_seq'::regclass);


--
-- TOC entry 4807 (class 2604 OID 16559)
-- Name: inventory_log log_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_log ALTER COLUMN log_id SET DEFAULT nextval('public.inventory_log_log_id_seq'::regclass);


--
-- TOC entry 4809 (class 2604 OID 16560)
-- Name: inventory_units unit_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_units ALTER COLUMN unit_id SET DEFAULT nextval('public.inventory_units_unit_id_seq'::regclass);


--
-- TOC entry 4813 (class 2604 OID 16561)
-- Name: manual_review review_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manual_review ALTER COLUMN review_id SET DEFAULT nextval('public.manual_review_review_id_seq'::regclass);


--
-- TOC entry 4817 (class 2604 OID 16562)
-- Name: products product_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products ALTER COLUMN product_id SET DEFAULT nextval('public.products_product_id_seq'::regclass);


--
-- TOC entry 4821 (class 2604 OID 16783)
-- Name: returns return_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.returns ALTER COLUMN return_id SET DEFAULT nextval('public.returns_return_id_seq'::regclass);


--
-- TOC entry 4818 (class 2604 OID 16563)
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- TOC entry 4853 (class 2606 OID 16623)
-- Name: brands brands_brand_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT brands_brand_name_key UNIQUE (brand_name);


--
-- TOC entry 4855 (class 2606 OID 16621)
-- Name: brands brands_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT brands_pkey PRIMARY KEY (brand_id);


--
-- TOC entry 4825 (class 2606 OID 16565)
-- Name: categories categories_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_name_key UNIQUE (name);


--
-- TOC entry 4827 (class 2606 OID 16567)
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (category_id);


--
-- TOC entry 4829 (class 2606 OID 16569)
-- Name: inventory_log inventory_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_log
    ADD CONSTRAINT inventory_log_pkey PRIMARY KEY (log_id);


--
-- TOC entry 4833 (class 2606 OID 16571)
-- Name: inventory_units inventory_units_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_units
    ADD CONSTRAINT inventory_units_pkey PRIMARY KEY (unit_id);


--
-- TOC entry 4835 (class 2606 OID 16573)
-- Name: manual_review manual_review_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manual_review
    ADD CONSTRAINT manual_review_pkey PRIMARY KEY (review_id);


--
-- TOC entry 4839 (class 2606 OID 16736)
-- Name: master_skus master_skus_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.master_skus
    ADD CONSTRAINT master_skus_pkey PRIMARY KEY (master_sku_id);


--
-- TOC entry 4843 (class 2606 OID 16579)
-- Name: products products_part_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_part_number_key UNIQUE (part_number);


--
-- TOC entry 4845 (class 2606 OID 16581)
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (product_id);


--
-- TOC entry 4857 (class 2606 OID 16788)
-- Name: returns returns_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.returns
    ADD CONSTRAINT returns_pkey PRIMARY KEY (return_id);


--
-- TOC entry 4841 (class 2606 OID 16724)
-- Name: master_skus unique_master_sku_code; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.master_skus
    ADD CONSTRAINT unique_master_sku_code UNIQUE (master_sku_id);


--
-- TOC entry 4837 (class 2606 OID 16583)
-- Name: manual_review unique_order_sku; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manual_review
    ADD CONSTRAINT unique_order_sku UNIQUE (order_id, sku);


--
-- TOC entry 4847 (class 2606 OID 16585)
-- Name: products unique_product_id; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT unique_product_id UNIQUE (product_id);


--
-- TOC entry 4831 (class 2606 OID 16587)
-- Name: inventory_log unique_serial_number; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_log
    ADD CONSTRAINT unique_serial_number UNIQUE (serial_number);


--
-- TOC entry 4849 (class 2606 OID 16589)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- TOC entry 4851 (class 2606 OID 16591)
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- TOC entry 4858 (class 2606 OID 16592)
-- Name: inventory_units inventory_units_assigned_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_units
    ADD CONSTRAINT inventory_units_assigned_by_user_id_fkey FOREIGN KEY (assigned_by_user_id) REFERENCES public.users(user_id);


--
-- TOC entry 4859 (class 2606 OID 16597)
-- Name: inventory_units inventory_units_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory_units
    ADD CONSTRAINT inventory_units_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(product_id) ON DELETE CASCADE;


--
-- TOC entry 4860 (class 2606 OID 16678)
-- Name: manual_review manual_review_resolved_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manual_review
    ADD CONSTRAINT manual_review_resolved_by_user_id_fkey FOREIGN KEY (resolved_by_user_id) REFERENCES public.users(user_id);


--
-- TOC entry 4861 (class 2606 OID 16629)
-- Name: products products_brand_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_brand_fkey FOREIGN KEY (brand) REFERENCES public.brands(brand_id);


--
-- TOC entry 4862 (class 2606 OID 16624)
-- Name: products products_brand_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_brand_id_fkey FOREIGN KEY (brand) REFERENCES public.brands(brand_id);


--
-- TOC entry 4863 (class 2606 OID 16602)
-- Name: products products_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id);


--
-- TOC entry 4864 (class 2606 OID 16737)
-- Name: products products_master_sku_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_master_sku_id_fkey FOREIGN KEY (master_sku_id) REFERENCES public.master_skus(master_sku_id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 4865 (class 2606 OID 16789)
-- Name: returns returns_original_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.returns
    ADD CONSTRAINT returns_original_unit_id_fkey FOREIGN KEY (original_unit_id) REFERENCES public.inventory_units(unit_id);


--
-- TOC entry 5021 (class 0 OID 0)
-- Dependencies: 5
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO majool_staff;


--
-- TOC entry 5022 (class 0 OID 0)
-- Dependencies: 235
-- Name: TABLE brands; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT ON TABLE public.brands TO majool_staff;


--
-- TOC entry 5024 (class 0 OID 0)
-- Dependencies: 221
-- Name: TABLE categories; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT ON TABLE public.categories TO majool_staff;


--
-- TOC entry 5026 (class 0 OID 0)
-- Dependencies: 222
-- Name: SEQUENCE categories_category_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.categories_category_id_seq TO majool_staff;


--
-- TOC entry 5027 (class 0 OID 0)
-- Dependencies: 223
-- Name: TABLE inventory_log; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.inventory_log TO majool_staff;


--
-- TOC entry 5029 (class 0 OID 0)
-- Dependencies: 224
-- Name: SEQUENCE inventory_log_log_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.inventory_log_log_id_seq TO majool_staff;


--
-- TOC entry 5030 (class 0 OID 0)
-- Dependencies: 225
-- Name: TABLE inventory_units; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.inventory_units TO majool_staff;


--
-- TOC entry 5031 (class 0 OID 0)
-- Dependencies: 225 5030
-- Name: COLUMN inventory_units.serial_number; Type: ACL; Schema: public; Owner: postgres
--

GRANT UPDATE(serial_number) ON TABLE public.inventory_units TO majool_staff;


--
-- TOC entry 5033 (class 0 OID 0)
-- Dependencies: 226
-- Name: SEQUENCE inventory_units_unit_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.inventory_units_unit_id_seq TO majool_staff;


--
-- TOC entry 5034 (class 0 OID 0)
-- Dependencies: 227
-- Name: TABLE manual_review; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.manual_review TO majool_staff;


--
-- TOC entry 5035 (class 0 OID 0)
-- Dependencies: 240
-- Name: TABLE manual_review_log_view; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT ON TABLE public.manual_review_log_view TO majool_staff;


--
-- TOC entry 5037 (class 0 OID 0)
-- Dependencies: 228
-- Name: SEQUENCE manual_review_review_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.manual_review_review_id_seq TO majool_staff;


--
-- TOC entry 5038 (class 0 OID 0)
-- Dependencies: 229
-- Name: TABLE master_skus; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT ON TABLE public.master_skus TO majool_staff;


--
-- TOC entry 5039 (class 0 OID 0)
-- Dependencies: 230
-- Name: TABLE products; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT ON TABLE public.products TO majool_staff;


--
-- TOC entry 5040 (class 0 OID 0)
-- Dependencies: 237
-- Name: TABLE msku_product_summary; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT ON TABLE public.msku_product_summary TO majool_staff;


--
-- TOC entry 5042 (class 0 OID 0)
-- Dependencies: 231
-- Name: SEQUENCE products_product_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.products_product_id_seq TO majool_staff;


--
-- TOC entry 5043 (class 0 OID 0)
-- Dependencies: 242
-- Name: TABLE returns; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.returns TO majool_staff;


--
-- TOC entry 5045 (class 0 OID 0)
-- Dependencies: 241
-- Name: SEQUENCE returns_return_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.returns_return_id_seq TO majool_staff;


--
-- TOC entry 5046 (class 0 OID 0)
-- Dependencies: 239
-- Name: TABLE temp_rose_view; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT ON TABLE public.temp_rose_view TO majool_staff;


--
-- TOC entry 5047 (class 0 OID 0)
-- Dependencies: 232
-- Name: TABLE users; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT ON TABLE public.users TO majool_staff;


--
-- TOC entry 5049 (class 0 OID 0)
-- Dependencies: 233
-- Name: SEQUENCE users_user_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.users_user_id_seq TO majool_staff;


--
-- TOC entry 5050 (class 0 OID 0)
-- Dependencies: 236
-- Name: TABLE view_product_details_readable; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT ON TABLE public.view_product_details_readable TO majool_staff;


--
-- TOC entry 5051 (class 0 OID 0)
-- Dependencies: 238
-- Name: TABLE view_serials_with_part_numbers; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT ON TABLE public.view_serials_with_part_numbers TO majool_staff;


--
-- TOC entry 2107 (class 826 OID 16612)
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT ON TABLES TO majool_staff;


-- Completed on 2025-06-19 15:23:47

--
-- PostgreSQL database dump complete
--


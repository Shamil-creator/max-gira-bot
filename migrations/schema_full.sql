--
-- PostgreSQL database dump
--

\restrict WmCi7FfzN8uEzWE22pCtBhrakxFzIj0PdoLI0aA5kc0lIQOpUJJoOSG7Qs944Nw

-- Dumped from database version 16.13 (Homebrew)
-- Dumped by pg_dump version 16.13 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
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
-- Name: bot_drafts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bot_drafts (
    draft_key text NOT NULL,
    scalar_value text,
    list_value jsonb,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.bot_drafts OWNER TO postgres;

--
-- Name: business_documents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.business_documents (
    id integer NOT NULL,
    id_business integer,
    file_id text,
    date_added date
);


ALTER TABLE public.business_documents OWNER TO postgres;

--
-- Name: business_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.business_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.business_documents_id_seq OWNER TO postgres;

--
-- Name: business_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.business_documents_id_seq OWNED BY public.business_documents.id;


--
-- Name: bussines; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bussines (
    id integer NOT NULL,
    name_company character varying(50) NOT NULL,
    id_form integer,
    square double precision,
    bid numeric(10,2),
    acceptance_certificate date,
    agreement character varying(50),
    state_company boolean,
    id_type_of_activity integer,
    end_date_agreement text,
    sheet_name text,
    surname text,
    first_name text,
    patronymic text,
    number_act integer DEFAULT 1
);


ALTER TABLE public.bussines OWNER TO postgres;

--
-- Name: bussines_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bussines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bussines_id_seq OWNER TO postgres;

--
-- Name: bussines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bussines_id_seq OWNED BY public.bussines.id;


--
-- Name: form_of_doing_business; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.form_of_doing_business (
    id integer NOT NULL,
    name character varying(13) NOT NULL
);


ALTER TABLE public.form_of_doing_business OWNER TO postgres;

--
-- Name: form_of_doing_business_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.form_of_doing_business_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.form_of_doing_business_id_seq OWNER TO postgres;

--
-- Name: form_of_doing_business_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.form_of_doing_business_id_seq OWNED BY public.form_of_doing_business.id;


--
-- Name: type_counter; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.type_counter (
    id integer NOT NULL,
    name text
);


ALTER TABLE public.type_counter OWNER TO postgres;

--
-- Name: type_counter_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.type_counter_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.type_counter_id_seq OWNER TO postgres;

--
-- Name: type_counter_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.type_counter_id_seq OWNED BY public.type_counter.id;


--
-- Name: type_of_activity; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.type_of_activity (
    id integer NOT NULL,
    name text
);


ALTER TABLE public.type_of_activity OWNER TO postgres;

--
-- Name: type_of_activity_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.type_of_activity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.type_of_activity_id_seq OWNER TO postgres;

--
-- Name: type_of_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.type_of_activity_id_seq OWNED BY public.type_of_activity.id;


--
-- Name: us_readings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.us_readings (
    id integer NOT NULL,
    number_counter text,
    counter_type_id integer,
    business_id integer
);


ALTER TABLE public.us_readings OWNER TO postgres;

--
-- Name: us_readings_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.us_readings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.us_readings_id_seq OWNER TO postgres;

--
-- Name: us_readings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.us_readings_id_seq OWNED BY public.us_readings.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    user_id character varying(30) NOT NULL,
    first_name character varying(50),
    second_name character varying(50),
    patronymic character varying(50),
    id_business integer,
    phone_number character(10),
    sheets_name text,
    username text
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: business_documents id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.business_documents ALTER COLUMN id SET DEFAULT nextval('public.business_documents_id_seq'::regclass);


--
-- Name: bussines id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bussines ALTER COLUMN id SET DEFAULT nextval('public.bussines_id_seq'::regclass);


--
-- Name: form_of_doing_business id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.form_of_doing_business ALTER COLUMN id SET DEFAULT nextval('public.form_of_doing_business_id_seq'::regclass);


--
-- Name: type_counter id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.type_counter ALTER COLUMN id SET DEFAULT nextval('public.type_counter_id_seq'::regclass);


--
-- Name: type_of_activity id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.type_of_activity ALTER COLUMN id SET DEFAULT nextval('public.type_of_activity_id_seq'::regclass);


--
-- Name: us_readings id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.us_readings ALTER COLUMN id SET DEFAULT nextval('public.us_readings_id_seq'::regclass);


--
-- Name: bot_drafts bot_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bot_drafts
    ADD CONSTRAINT bot_drafts_pkey PRIMARY KEY (draft_key);


--
-- Name: business_documents business_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.business_documents
    ADD CONSTRAINT business_documents_pkey PRIMARY KEY (id);


--
-- Name: bussines bussines_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bussines
    ADD CONSTRAINT bussines_pkey PRIMARY KEY (id);


--
-- Name: form_of_doing_business form_of_doing_business_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.form_of_doing_business
    ADD CONSTRAINT form_of_doing_business_pkey PRIMARY KEY (id);


--
-- Name: type_of_activity name; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.type_of_activity
    ADD CONSTRAINT name UNIQUE (name);


--
-- Name: type_counter type_counter_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.type_counter
    ADD CONSTRAINT type_counter_pkey PRIMARY KEY (id);


--
-- Name: type_of_activity type_of_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.type_of_activity
    ADD CONSTRAINT type_of_activity_pkey PRIMARY KEY (id);


--
-- Name: us_readings us_readings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.us_readings
    ADD CONSTRAINT us_readings_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: idx_bot_drafts_updated_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_bot_drafts_updated_at ON public.bot_drafts USING btree (updated_at);


--
-- Name: business_documents business_documents_id_business_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.business_documents
    ADD CONSTRAINT business_documents_id_business_fkey FOREIGN KEY (id_business) REFERENCES public.bussines(id);


--
-- Name: bussines bussines_id_form_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bussines
    ADD CONSTRAINT bussines_id_form_fkey FOREIGN KEY (id_form) REFERENCES public.form_of_doing_business(id);


--
-- Name: bussines bussines_id_type_of_activity_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bussines
    ADD CONSTRAINT bussines_id_type_of_activity_fkey FOREIGN KEY (id_type_of_activity) REFERENCES public.type_of_activity(id);


--
-- Name: us_readings us_readings_business_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.us_readings
    ADD CONSTRAINT us_readings_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.bussines(id);


--
-- Name: us_readings us_readings_counter_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.us_readings
    ADD CONSTRAINT us_readings_counter_type_id_fkey FOREIGN KEY (counter_type_id) REFERENCES public.type_counter(id);


--
-- Name: users users_id_business_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_id_business_fkey FOREIGN KEY (id_business) REFERENCES public.bussines(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict WmCi7FfzN8uEzWE22pCtBhrakxFzIj0PdoLI0aA5kc0lIQOpUJJoOSG7Qs944Nw


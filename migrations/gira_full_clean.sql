--
-- PostgreSQL database dump
--


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

ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_id_business_fkey;
ALTER TABLE IF EXISTS ONLY public.us_readings DROP CONSTRAINT IF EXISTS us_readings_counter_type_id_fkey;
ALTER TABLE IF EXISTS ONLY public.us_readings DROP CONSTRAINT IF EXISTS us_readings_business_id_fkey;
ALTER TABLE IF EXISTS ONLY public.bussines DROP CONSTRAINT IF EXISTS bussines_id_type_of_activity_fkey;
ALTER TABLE IF EXISTS ONLY public.bussines DROP CONSTRAINT IF EXISTS bussines_id_form_fkey;
ALTER TABLE IF EXISTS ONLY public.business_documents DROP CONSTRAINT IF EXISTS business_documents_id_business_fkey;
DROP INDEX IF EXISTS public.idx_bot_drafts_updated_at;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE IF EXISTS ONLY public.us_readings DROP CONSTRAINT IF EXISTS us_readings_pkey;
ALTER TABLE IF EXISTS ONLY public.type_of_activity DROP CONSTRAINT IF EXISTS type_of_activity_pkey;
ALTER TABLE IF EXISTS ONLY public.type_counter DROP CONSTRAINT IF EXISTS type_counter_pkey;
ALTER TABLE IF EXISTS ONLY public.type_of_activity DROP CONSTRAINT IF EXISTS name;
ALTER TABLE IF EXISTS ONLY public.form_of_doing_business DROP CONSTRAINT IF EXISTS form_of_doing_business_pkey;
ALTER TABLE IF EXISTS ONLY public.bussines DROP CONSTRAINT IF EXISTS bussines_pkey;
ALTER TABLE IF EXISTS ONLY public.business_documents DROP CONSTRAINT IF EXISTS business_documents_pkey;
ALTER TABLE IF EXISTS ONLY public.bot_drafts DROP CONSTRAINT IF EXISTS bot_drafts_pkey;
ALTER TABLE IF EXISTS public.us_readings ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.type_of_activity ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.type_counter ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.form_of_doing_business ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.bussines ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.business_documents ALTER COLUMN id DROP DEFAULT;
DROP TABLE IF EXISTS public.users;
DROP SEQUENCE IF EXISTS public.us_readings_id_seq;
DROP TABLE IF EXISTS public.us_readings;
DROP SEQUENCE IF EXISTS public.type_of_activity_id_seq;
DROP TABLE IF EXISTS public.type_of_activity;
DROP SEQUENCE IF EXISTS public.type_counter_id_seq;
DROP TABLE IF EXISTS public.type_counter;
DROP SEQUENCE IF EXISTS public.form_of_doing_business_id_seq;
DROP TABLE IF EXISTS public.form_of_doing_business;
DROP SEQUENCE IF EXISTS public.bussines_id_seq;
DROP TABLE IF EXISTS public.bussines;
DROP SEQUENCE IF EXISTS public.business_documents_id_seq;
DROP TABLE IF EXISTS public.business_documents;
DROP TABLE IF EXISTS public.bot_drafts;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bot_drafts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_drafts (
    draft_key text NOT NULL,
    scalar_value text,
    list_value jsonb,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: business_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_documents (
    id integer NOT NULL,
    id_business integer,
    file_id text,
    date_added date,
    file_name text
);


--
-- Name: business_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.business_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: business_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.business_documents_id_seq OWNED BY public.business_documents.id;


--
-- Name: bussines; Type: TABLE; Schema: public; Owner: -
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
    number_act integer DEFAULT 1,
    phone text,
    number_act_ku integer DEFAULT 0,
    director_title text
);


--
-- Name: bussines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bussines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bussines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bussines_id_seq OWNED BY public.bussines.id;


--
-- Name: form_of_doing_business; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.form_of_doing_business (
    id integer NOT NULL,
    name character varying(13) NOT NULL
);


--
-- Name: form_of_doing_business_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.form_of_doing_business_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: form_of_doing_business_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.form_of_doing_business_id_seq OWNED BY public.form_of_doing_business.id;


--
-- Name: type_counter; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.type_counter (
    id integer NOT NULL,
    name text
);


--
-- Name: type_counter_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.type_counter_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: type_counter_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.type_counter_id_seq OWNED BY public.type_counter.id;


--
-- Name: type_of_activity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.type_of_activity (
    id integer NOT NULL,
    name text
);


--
-- Name: type_of_activity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.type_of_activity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: type_of_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.type_of_activity_id_seq OWNED BY public.type_of_activity.id;


--
-- Name: us_readings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.us_readings (
    id integer NOT NULL,
    number_counter text,
    counter_type_id integer,
    business_id integer
);


--
-- Name: us_readings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.us_readings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: us_readings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.us_readings_id_seq OWNED BY public.us_readings.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: business_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_documents ALTER COLUMN id SET DEFAULT nextval('public.business_documents_id_seq'::regclass);


--
-- Name: bussines id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bussines ALTER COLUMN id SET DEFAULT nextval('public.bussines_id_seq'::regclass);


--
-- Name: form_of_doing_business id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.form_of_doing_business ALTER COLUMN id SET DEFAULT nextval('public.form_of_doing_business_id_seq'::regclass);


--
-- Name: type_counter id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.type_counter ALTER COLUMN id SET DEFAULT nextval('public.type_counter_id_seq'::regclass);


--
-- Name: type_of_activity id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.type_of_activity ALTER COLUMN id SET DEFAULT nextval('public.type_of_activity_id_seq'::regclass);


--
-- Name: us_readings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.us_readings ALTER COLUMN id SET DEFAULT nextval('public.us_readings_id_seq'::regclass);


--
-- Data for Name: bot_drafts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.bot_drafts (draft_key, scalar_value, list_value, updated_at) FROM stdin;
user:237593021:list_cold_water	\N	["12"]	2026-03-22 22:47:53.121164+03
admin_access:237593021	1	\N	2026-03-24 11:27:32.214415+03
admin_access:79513681	1	\N	2026-03-24 22:51:47.793234+03
user:109821500:meters	hw,cw,el	\N	2026-03-25 01:16:42.341533+03
admin_access:228004937	1	\N	2026-03-25 17:16:56.49646+03
user:87411656:meters	hw,cw,el	\N	2026-03-27 22:45:53.865959+03
user:262267428:meters	hw,cw,el	\N	2026-03-28 02:58:20.741826+03
mr_submissions:2026-03:biz:9	{"312": "57665"}	\N	2026-03-30 00:34:43.912948+03
\.


--
-- Data for Name: business_documents; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.business_documents (id, id_business, file_id, date_added, file_name) FROM stdin;
39	9	https://fd.oneme.ru/getfile?sig=uh9jxM46Rn3vsw9L1IwB1mCjEiPiA66wXRljdVJK3bHuD6CC3E-SXnHhY3ABOUMDlQJNHLgFhNOfzMyttxb1tQ&expires=1777249262544&clientType=3&id=3034321458&userId=186428021	2026-03-28	Счет на оплату 03.2026.docx
38	9	https://fd.oneme.ru/getfile?sig=buK7fs7b8W4pyRSHnOBwTJSG7ZKcTZu5H_or4zVfnutYZvcLPj6a5tWEAgo5z61OB8dxExguyNP6OmzcLCAm2w&expires=1777249262538&clientType=3&id=3034202422&userId=186428021	2026-03-28	Счет на оплату 03.2026.docx
37	8	https://fd.oneme.ru/getfile?sig=zGqk7PPyrPqlwPD3IdCw1uBAAekw-0tmVv8j5rD5oBX8ISqIsyo4StupDSleWIaaVMvxf5RGpvcAL2du2ffbUA&expires=1777249262534&clientType=3&id=3029307187&userId=186428021	2026-03-28	Счет на оплату 03.2026.docx
40	9	https://fd.oneme.ru/getfile?sig=P1OKKoIKiTPAOr8Aq0roadmRoj1JMpdf_HHO1vvX_ZEeuFJdIC_MPoFPbxIzAohTyeOmasIk6-TElLVMqnQrDw&expires=1777287828764&clientType=3&id=3042706062&userId=186428021	2026-03-28	Счет на оплату 04.2026.xlsx
41	9	https://fd.oneme.ru/getfile?sig=TFo6P1ejvD13hC8c-CbBSdeF9gLzuwcnab2yxeZjuba3-83Utl5e66DB1wzqZnpFlvFkRtbk477cFrKDSl9lEw&expires=1777287828756&clientType=3&id=3030636127&userId=186428021	2026-03-28	Счет на оплату 04.2026.xlsx
42	8	https://fd.oneme.ru/getfile?sig=0j-zEz7IDoNAfhWvUOxuwbCGt_jE2e6x8bGS9uewNuKjmX5rQIoEAtlYkcnNNQtnXS5eU-XWSTBhpSPC-bb27Q&expires=1777287828758&clientType=3&id=3036348495&userId=186428021	2026-03-28	Счет на оплату 04.2026.xlsx
44	9	https://fd.oneme.ru/getfile?sig=7B9al-cdwtTZHjVFkfuRzqSzNUmxGO05IBi8YAdXpTBpIJ6LX8jcWHm-aBk-0vXDO_SZYY4kuOPCVw4vy928kA&expires=1777288309500&clientType=3&id=3034847702&userId=186428021	2026-03-28	Счет на оплату 04.2026.xlsx
43	8	https://fd.oneme.ru/getfile?sig=grUtGpcPi22_ykW71ikxXIg2OXJ_Utc75yzMlBMTo_0wcuEWm_6lojKW-JcjvK7I47k0mPqmik29aAl1U5e8Fw&expires=1777288309494&clientType=3&id=3033224717&userId=186428021	2026-03-28	Счет на оплату 04.2026.xlsx
45	9	https://fd.oneme.ru/getfile?sig=X8IA8oMT7pNJwVGoZcFyrXncoiwTtP7EUT6NZgvgvGdZYj4XiTtDvmGg2exMMnlq5BTQAdeNTIQ7tSKCbf8JOA&expires=1777288309559&clientType=3&id=3027091156&userId=186428021	2026-03-28	Счет на оплату 04.2026.xlsx
46	9	https://fd.oneme.ru/getfile?sig=xxQq_PPb_XSAOxW6gL3UefuQonhXtzkCWihiYlmLfV50YyVfisogOGLEcySo35f4nS1AnyVGkewtZksiRCyADw&expires=1777288494566&clientType=3&id=3037208057&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
47	8	https://fd.oneme.ru/getfile?sig=D0b_fnMQat2-6P0qhw4mixwlduGInXntusYEjuFaJV0CucqG03MANcj4gnKTPfDsCHOlffw0sgCaChnZWK_q6A&expires=1777288494754&clientType=3&id=3039124725&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
48	9	https://fd.oneme.ru/getfile?sig=oZClcwnOvODCQubp1YMczfmeqlnnskP5p_t7ce5aRhoH-g1VhBL0Nbt8woK8Ig_eamf8Hp7rQBsg5Ryabu4juA&expires=1777288496825&clientType=3&id=3040276731&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
49	8	https://fd.oneme.ru/getfile?sig=tPJrtETp14xpN3Wg_MjFT7Pcy4oSjpf9o3y93Z5rl9ELESO_1YhMLYuKCNtCoWPYadDd1nk6pAJ8WkzKCoN16A&expires=1777289866041&clientType=3&id=3022228320&userId=186428021	2026-03-28	Акт 03.2026.xlsx
50	9	https://fd.oneme.ru/getfile?sig=QuPkw_tFwqf4IXlQE_bzhwwfKt_41NhH4C7kaw7Lxtq15dAWGC6UpJ-nmDphWjxX_G4AYQ-5HRiqlHzNjP009Q&expires=1777289866100&clientType=3&id=3034390875&userId=186428021	2026-03-28	Акт 03.2026.xlsx
51	9	https://fd.oneme.ru/getfile?sig=a7i-OnH5i0kooLpRpHPShpeYXW_lFCurh2FUPfpvJiIVZx_MDSNWCY2FIiYUZD1hy0TbVKnu6cQjjbQloGDn5Q&expires=1777289866119&clientType=3&id=3025305652&userId=186428021	2026-03-28	Акт 03.2026.xlsx
52	8	https://fd.oneme.ru/getfile?sig=Ssg8sukNPH_FfhqndTk9fcAh7o-FGZBF7JSe2Q_QTyNiX7LWJ4kFgbw3oNyxMU15Y9qJq1ShJvEHwJCkEjTxag&expires=1777290339349&clientType=3&id=3023877099&userId=186428021	2026-03-28	Акт 03.2026.xlsx
53	9	https://fd.oneme.ru/getfile?sig=7KeMwtWW4B5Pt_I8raL0A3nuV9oZ8BzlGsKehpmwC9Sj0L3hSXtSVa1RQHHdiLZAGx8jbPYsDytHqLLHIzH0iA&expires=1777290339394&clientType=3&id=3037300705&userId=186428021	2026-03-28	Акт 03.2026.xlsx
54	9	https://fd.oneme.ru/getfile?sig=6m90KV_HGOTpxk9iNXiII_SM8leyGzA-1yaXP6lM45YIP4U_5tYIkqm1J0AhCl9SMBh5hpvZXIuXg-bnbP9feA&expires=1777290339447&clientType=3&id=3037300961&userId=186428021	2026-03-28	Акт 03.2026.xlsx
55	8	https://fd.oneme.ru/getfile?sig=2xhdlWF3CEBnhafsoSeBaQBkzp9aUo8up9DyRXoDLBaZ_uNIJYqLikHE2TtLAYNboVkt6nAtyiiTwu507OpP7g&expires=1777290553129&clientType=3&id=3038320210&userId=186428021	2026-03-28	Акт 03.2026.xlsx
56	9	https://fd.oneme.ru/getfile?sig=TVmH8RWMm_Y7r9FfZuUQHZp2kt6bsP1bV3I6vEqNmMciS01GqNmJtDVm0SE5Lrltr-lq1vBpR1RDoXm9Ttf6FQ&expires=1777290553152&clientType=3&id=3035604747&userId=186428021	2026-03-28	Акт 03.2026.xlsx
57	9	https://fd.oneme.ru/getfile?sig=r-QUKF7evkQ82cbxVaz0vRZ7miOYRUy9zrHzPwZzQiFCxyIPbRL9hX8vbr7zWTKK8b4399dUG9n9_Z6oFxSFJg&expires=1777290553212&clientType=3&id=3038973728&userId=186428021	2026-03-28	Акт 03.2026.xlsx
58	9	https://fd.oneme.ru/getfile?sig=aD6fKAu38AiLHfa3bYJGG2HIIWLs_kH4u1zMfXl2mvsIv4dvFpiO5SCujWn8qtHw0kq4LGkizfM3Xfui570AvA&expires=1777290707519&clientType=3&id=3031663275&userId=186428021	2026-03-28	Акт 03.2026.xlsx
59	8	https://fd.oneme.ru/getfile?sig=JwycsBEppkUeZBhf5SyE7E9b2OK3m7i2vuaamxgWkrtSd2OzffdjwmCcty0OZ4GQqnfMchXmBTwxA5EPRoD5nw&expires=1777290707579&clientType=3&id=3028202403&userId=186428021	2026-03-28	Акт 03.2026.xlsx
60	9	https://fd.oneme.ru/getfile?sig=_Apxvd3phBwLXlAmqFaQxItBshhHhQUbqeAp43Wuodes05TC7eEkMVTE95ilYTmq8ICG_GtgxZx2rSbBMYERtg&expires=1777290707783&clientType=3&id=3039437295&userId=186428021	2026-03-28	Акт 03.2026.xlsx
61	9	https://fd.oneme.ru/getfile?sig=02mzv564yvBA-xqk6VlZG_VqCUwUWnc0p41D6GXZD_J83uV-9H_Z91VAAK1XkixX32g6FQy52iS2AiuaaCp9Mw&expires=1777291554830&clientType=3&id=3039249636&userId=186428021	2026-03-28	Акт 03.2026.xlsx
62	9	https://fd.oneme.ru/getfile?sig=eQETjCGciMQL1b1Sl1PJkPW_iADSqL9VmvGdAf9FofO1RXMUXodhRs-UYrYLas0SGsYjayiqE9A7nmqjB4tVTA&expires=1777291554851&clientType=3&id=3031913972&userId=186428021	2026-03-28	Акт 03.2026.xlsx
63	8	https://fd.oneme.ru/getfile?sig=eHjfUPoZeugfQ75tLrykGoNxHLfDaWhecY76iiUD-A3h1agpDsrFi8yvyi4CIBdTgHQwUv0fCv_M4ztu5fqLdw&expires=1777291554969&clientType=3&id=3035133142&userId=186428021	2026-03-28	Акт 03.2026.xlsx
64	8	https://fd.oneme.ru/getfile?sig=ySLAttT2rWW4q6YbLhKk0g-KgD2Z-vdRutpGPwRBrd1O1D1wEsb07v9YVLVuJlZJ9xnKypaZeWxHAm5Fl699Jw&expires=1777291871689&clientType=3&id=3025009852&userId=186428021	2026-03-28	Акт 03.2026.pdf
66	9	https://fd.oneme.ru/getfile?sig=U6a1um-h59AEN0OFg-A4txgqoKQdoeic_bpYom2t8jGx0wIeRAA56rx7mZecYSMVaUSIr9VhBjqwtQ60QqjTKA&expires=1777291871726&clientType=3&id=3033899202&userId=186428021	2026-03-28	Акт 03.2026.pdf
65	9	https://fd.oneme.ru/getfile?sig=_3qNFTKowA-iEclq6LOJOr01dMlK80UqymCoDab-zUr_ERfpT8F6fg-614NAfv94RHrLjxfwrr7e7YV5USHHnw&expires=1777291871728&clientType=3&id=3039532783&userId=186428021	2026-03-28	Акт 03.2026.pdf
67	8	https://fd.oneme.ru/getfile?sig=7HH6M5_kXztZUaAIVJa-763svL531B0N_Hipfy9-USUidDhMY5ZiHVETBj26-BFC-lhqrcUVSVy1qaTC6w65CQ&expires=1777292487201&clientType=3&id=3040056079&userId=186428021	2026-03-28	Акт 03.2026.xlsx
68	9	https://fd.oneme.ru/getfile?sig=Xdzdna3YllEJqsDy_5DWNMpqwlJwhR9dqbqfaA20tYj2ZbSE9Iw-sBRG93_6wUfBTk4CMtbVJA__5ONRwHCQxQ&expires=1777292487216&clientType=3&id=3036778515&userId=186428021	2026-03-28	Акт 03.2026.xlsx
69	9	https://fd.oneme.ru/getfile?sig=EpG8PySGKd989l_bVUVIwFU7arwGEsTe0VtMKmtpUczx8f0phRNKF8GpFsmxZU_pgWpTONEB9Nbax6aZBPUdow&expires=1777292487219&clientType=3&id=3036778259&userId=186428021	2026-03-28	Акт 03.2026.xlsx
70	9	https://fd.oneme.ru/getfile?sig=GZVmg4mqOLvQRoDkBKN7wp8TYqY6_-lztxVakmllSRSn7x954S0oDu6zQYYjIYtg5G3btngKfDxljuYInm7_Xw&expires=1777292594025&clientType=3&id=3030594712&userId=186428021	2026-03-28	Акт 03.2026.xlsx
71	8	https://fd.oneme.ru/getfile?sig=pC5lIMh6_cboBK_EvYwQ7RO-PHvM3fWmGdCAKkDiry2fyZG997K3ySPa-AlXY_5SB5MbxTauuzmgJUfr76u1kg&expires=1777292594073&clientType=3&id=3031643806&userId=186428021	2026-03-28	Акт 03.2026.xlsx
72	9	https://fd.oneme.ru/getfile?sig=WbNSwbQxuedCHnRvzJTK2teBEKL_6fZ-JhcwJrC5SAjwLqvPQ8K0aNBv2nK8os4abuKqNQKvrM3THA4QCf1Rfg&expires=1777292594096&clientType=3&id=3036465342&userId=186428021	2026-03-28	Акт 03.2026.xlsx
73	9	https://fd.oneme.ru/getfile?sig=xOYYell9SJjActdoJdyFrQUARbLPy_4cctklJ6JUg6z6UQBbQu-rf2UUz2XocMottUaYcy7i39s7WQXB1Htgwg&expires=1777292693634&clientType=3&id=3036091160&userId=186428021	2026-03-28	Акт 03.2026.xlsx
74	8	https://fd.oneme.ru/getfile?sig=8PpIMnbjRTEm-Z67XQb5jcP-axqOuW035Q7vl4MysQM733aJcHiBw2aLO5yTigy62BSvCfpowWNg9uHcM-KsSA&expires=1777292693639&clientType=3&id=3038780449&userId=186428021	2026-03-28	Акт 03.2026.xlsx
75	9	https://fd.oneme.ru/getfile?sig=Zs3qBTUoqjl5xhaDsRIw88EvoehO386rmSELcckD7I8pqrk_qO2FJGFQ6VqyP3xEgSKYrF90_1tQJYyY8b-gSw&expires=1777292693681&clientType=3&id=3034414391&userId=186428021	2026-03-28	Акт 03.2026.xlsx
76	9	https://fd.oneme.ru/getfile?sig=oXb2KObD8yGYoiDifjMw8pZtXdLfzlLueRw3q4EbQaIf_kZLnSJFq3gNurGBHy3x3VTsAAwa8tvsdaY2QmXUnA&expires=1777292966560&clientType=3&id=3023824863&userId=186428021	2026-03-28	Акт 03.2026.xlsx
77	9	https://fd.oneme.ru/getfile?sig=yno4f2xi1ceOLC0b60Wb2foK7mD4nvsGGcyC1hdtqg_zLBWPSDBvZ5mtWE7iHmbRp9IEIszU-mEVkxBWBvNMIQ&expires=1777292966665&clientType=3&id=3038802209&userId=186428021	2026-03-28	Акт 03.2026.xlsx
78	8	https://fd.oneme.ru/getfile?sig=FZosOgP6XtTuW4LdBxW6kDY8usfWtAL_jeAtrM6r4fXOhZsIUpKB8hX-zUdrEL306nr-bmKgBjzSzgn7RXELKA&expires=1777292966668&clientType=3&id=3023824607&userId=186428021	2026-03-28	Акт 03.2026.xlsx
79	8	https://fd.oneme.ru/getfile?sig=Ey9zXU-kqYYdZl39pFP-LAw7qh21oZ1NXkZ5o9G-1tBcjdHJ0ziBJWOxNnBi4YSgYVekeAu4wa5KKTNenAZEpg&expires=1777293729927&clientType=3&id=3032417206&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
80	9	https://fd.oneme.ru/getfile?sig=IodWpbInCaIpe6k9-VlA8AgmgjPEvFroOzrwx8uwTT4yPPn97_nEzTZ0ANkvppg7q8VRZBXA2LVAwA6lHYCHeQ&expires=1777293729977&clientType=3&id=3041061809&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
81	9	https://fd.oneme.ru/getfile?sig=C82HKiLdXFi5vgjpOMFlALd00GLxVZCxzQmDbqR_Tlel9buo4MdE3qv7sSrLcL39FyWcBsQUHoMma_6FXyiCpw&expires=1777293730017&clientType=3&id=3026326440&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
82	8	https://fd.oneme.ru/getfile?sig=HJm2CSRdx5dDQ_iCEOMnX9b4-QfP3OB2bycv0ZkpJ2Eae_vmL8PYTZ-FnfDKZnXuC7PrT5M4AzPcS28aW2pn-Q&expires=1777294431512&clientType=3&id=3031075279&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
83	9	https://fd.oneme.ru/getfile?sig=APEJTVRffWwhUOL5jnlodrPxByLsutBpuVt5EyHlBnsX6T0f6Rb4qfNI6l3VdkdtmQExcE5yFJ2iDeS8TBV7Tg&expires=1777294431545&clientType=3&id=3038599458&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
84	9	https://fd.oneme.ru/getfile?sig=M11X3YKEIqSQA-YGyuID3OpWaaZqxKGCNrmNIeUOkpSJYdbgFWITavhGdTYNyzhb1Lj7s3ITLajjPFv_ScnVfw&expires=1777294431567&clientType=3&id=3034840318&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
86	9	https://fd.oneme.ru/getfile?sig=nkK7m5WhLyOApZME5osQNddB3TF1OPFSQ-Ax_DIWXcfGnpupMrU0b86DzPfNN8SS04fTqot2MpDDGuxUYqXYIw&expires=1777294949739&clientType=3&id=3045189390&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
85	9	https://fd.oneme.ru/getfile?sig=F5lbnBZxrWHAJzTrMSPOVXjV5px1BW3YFzaf5BB9-U2Q2UJfRlRg2stoNY2LIKEntRgIEt-nVWbART-uPZXepg&expires=1777294949741&clientType=3&id=3033404378&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
87	8	https://fd.oneme.ru/getfile?sig=6LYYUwm80c7bBtcXyrp-2cMB4HIfi6vif5gjRuMA7jXq4YLkO1J4Lvpmofpxkfulbld9QQzLMuGDF4GjI6yM4w&expires=1777294949841&clientType=3&id=3033397735&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
88	9	https://fd.oneme.ru/getfile?sig=lSrlueAxtkEYNpcdiOzO0A0tjIiXJOnfZO5l5zJOIOz7DSEzI2n_JzujWM_tSLA436EhEzzInQuAFE0ADmskgQ&expires=1777295774790&clientType=3&id=3034132296&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
89	8	https://fd.oneme.ru/getfile?sig=khiil2Q0O_k45d-37AT89QbXGrWZb8ZGk12VxqkKtGPoWlIHk5x1LNtASAX5CfxjZcG2e3KArM5DcCJcJjjnOA&expires=1777295774807&clientType=3&id=3031119205&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
90	9	https://fd.oneme.ru/getfile?sig=-4sjLey7C-YgClx9yAbDA_9CDniY5_Gs2OBdEU6IJnkmf5OMTMyQw3RFWQipdn1Mvctb-SeeNmua0cDz7TTL5g&expires=1777295774863&clientType=3&id=3031118949&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
91	9	https://fd.oneme.ru/getfile?sig=hOIaP2ai4cFkFb41RN-1XELMCD-lcmnVGXsM1QjtQGfRCNmwKK2II3BhCiEcoQ9fxQgqqAYPZtifkfiW_lPMsQ&expires=1777296309976&clientType=3&id=3035599845&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
92	9	https://fd.oneme.ru/getfile?sig=INmErVczE5Cab7AC1E5EM0X4bAnj_S-InPsbVwUJPTSylKbBSvs9pGU4AGNaAGDiauL0LpU_ILkEXU-fapQ8Uw&expires=1777296310018&clientType=3&id=3035461854&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
93	8	https://fd.oneme.ru/getfile?sig=LYpO15ECKSPOr3fQnPnesqZ_iVyKwiBZboPXGOUlMyCmEMijnTLEDGBJ7um8md5QoUziQh-Rqznu5qcIhYnxdA&expires=1777296310240&clientType=3&id=3031968988&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
94	9	https://fd.oneme.ru/getfile?sig=_vgw8b66Acxuv181BXkdceHOmljnqXfv6A0aljbXC7YNoFocQ9lkDjFhvrdohUf2XYRzbxQe25iOT79AKH7rrw&expires=1777296741791&clientType=3&id=3034146722&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
95	9	https://fd.oneme.ru/getfile?sig=A1UBAHJ014vzWf4dUQrkD7uvjtFerkNXanAKLERnKvv8HlSGeC3Py1Rxdy2THi3j1CEe_OIdqp4sTNe1Be59eQ&expires=1777296741817&clientType=3&id=3026128248&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
96	8	https://fd.oneme.ru/getfile?sig=yjm7lTHZaCflztIGhzvlhcjBzeMKUkYEKA9rL3bH6hUe87zXCe5uFBrShcbEpSj40XS4MXXBUB3Vy7lNWYxYrg&expires=1777296741846&clientType=3&id=3042698650&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
97	8	https://fd.oneme.ru/getfile?sig=C031YqewpBfN8QzIGyYSmqRhNq9IY0Wdz66ZunMbDRZT0-iw1mDXxqTJwLCdcQcuFMbKYiJg6s45TtFIMkoMvw&expires=1777297005975&clientType=3&id=3034668911&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
98	9	https://fd.oneme.ru/getfile?sig=QTYPKVDOmvh7s1ynbOViesZbCUFXhnlI6xXHPAWmWcKmAhskWux_VipUp8TMnda4OfRzK37vMQ40LCPLnincZQ&expires=1777297006007&clientType=3&id=3024965533&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
99	9	https://fd.oneme.ru/getfile?sig=dXreOx-KOaiA9u64JcILJZT3GQEC9V_orkdhX_gjm5Pngq0BMuEqD7Iy4TnPQZypKpjPs1lYG7zF--Opk45PFA&expires=1777297006017&clientType=3&id=3024965277&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
100	9	https://fd.oneme.ru/getfile?sig=SxOSF4T9xzRYSQsjZdyCYhOF4uNTQpYsyxM_u4vLq9vmQPZ22-VKzq_suXEjcVWAzW-Xaqag7wRXNg076D6Xpw&expires=1777297245477&clientType=3&id=3039577166&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
101	8	https://fd.oneme.ru/getfile?sig=yXYnZBhl3Mae4ZlHQAqfYOy_fR189-bxbU7S7pSOjCFVeys6KXRq3v1-7CMItAdPuY638h7ibeIDQLiVNl3K2w&expires=1777297245485&clientType=3&id=3025946164&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
102	9	https://fd.oneme.ru/getfile?sig=gsk6lqoPYJFrFc3-g5ZlcmHcZ23oIbDEcls0uqIQFujOCL4A0hvA7_XyMoIDg_UZG2-pV2_8UauphjvQj8Pexg&expires=1777297245488&clientType=3&id=3034021887&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
103	9	https://fd.oneme.ru/getfile?sig=HfL1p8abzrdueLQxsIHyS1dOg4gEMcwadyY8Sk4FpJuyfu36JalPKsOmsnVmzx__pcx8JyBRMF0l6Vtm7cjGOA&expires=1777297437967&clientType=3&id=3034910706&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
104	9	https://fd.oneme.ru/getfile?sig=8pJOlEiw-HG9N0C4XV9DVXmEGESLUI_qprmc9aKUYP7mtNDu_XK2Mg--lB-5Gtv0tvfuAgHsmip_J8NNGWMjGA&expires=1777297438020&clientType=3&id=3037836234&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
105	8	https://fd.oneme.ru/getfile?sig=ZeIehhCzJeaMQ62Uswe-AyLBeDBl36nIAn1FQp6PDPDI-dDWlgzTsaSI0mE4I-O1nR5aF77K194-D9N8srZlEw&expires=1777298130998&clientType=3&id=3040047343&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
106	9	https://fd.oneme.ru/getfile?sig=j_SRVOPHS-BrwH0jYliK2plWyl0q2sOU2KundZxIkxgB8XyXRnvlY_JmUmJoaMMMlyQdz1hwIAwyAalgkWj1iA&expires=1777298160993&clientType=3&id=3026014004&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
107	9	https://fd.oneme.ru/getfile?sig=ljXWqqwfARXYgXjQhCRiIlLEQOpihrf9-PAb5NJgvaH_5lfZOQxAq22hi_R59sddzEp6kdvy7AkzahjmfGUmUA&expires=1777298190982&clientType=3&id=3043663502&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
108	8	https://fd.oneme.ru/getfile?sig=7V2pMsQVnydIlO3tRl5nx87LAWXE34nlFepPAVwhJ8ELXc-VjBYpTbpD3rVaSTuxiuwsFluMBdGdKUCguq1uBw&expires=1777300777871&clientType=3&id=3032478891&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
109	9	https://fd.oneme.ru/getfile?sig=LULQTkd9H0iNSTYoeURPLaIuS7hCvSRMlkMK6kBjhlLeKIbcVEkxuHLOpITIkG8JUY8YcN6fo3Xyvx9zfKE0ww&expires=1777300807689&clientType=3&id=3027029881&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
110	9	https://fd.oneme.ru/getfile?sig=0E9tRBIZ72dFBcH7CXmaSY4lj0ZRWvhRCVbpvORat_IvB-wliopVQqajn_fNAxB-NakqDVxSu5HgvPRuJAi4yw&expires=1777300837802&clientType=3&id=3038144481&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
111	8	https://fd.oneme.ru/getfile?sig=gihnR6vN_DfVZIjvjOnfr4PlMZSt0uiyXT4fyh-WOE41vD3y07EW2MIXyWzkHThx6wz4d2yDbO_tNweXDczhDw&expires=1777301292255&clientType=3&id=3031645391&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
112	9	https://fd.oneme.ru/getfile?sig=BhA6rNAeAspBXsaexDsKekmA17n94UQVfx3XcEezFRlSjPWkPcb0pkaPOxM9seJVuwV4Tk78HREmsQBmYXUEGg&expires=1777301322186&clientType=3&id=3029694210&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
113	9	https://fd.oneme.ru/getfile?sig=VXz6N3eYDkREcB5KIFhToVrp4R8dCqT_Gwd-6wpk5Hayv-Va66Cg50FrG5zyDS7iFQG_jeIZMTf_HtTW22r_zQ&expires=1777301352154&clientType=3&id=3035137591&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
114	8	https://fd.oneme.ru/getfile?sig=3ccYhV1UFyCJt4uLGpiWql5sdLuDRCUDpjyF1YuxEuKjfFeV3cF_mm-RcP93R3DOyNVq8Gy03Nct6DZp-4HlwQ&expires=1777301438578&clientType=3&id=3034522786&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
115	9	https://fd.oneme.ru/getfile?sig=z-ctMKs_n3wkVKQyxzo67I0f2LmNUk3iaALUAx6yUQVt4uZEGhAx84-guwgY-qi-1l0jQtOgSAMv8zp-rq-vdQ&expires=1777301468641&clientType=3&id=3037317626&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
116	9	https://fd.oneme.ru/getfile?sig=UtVPpf9M_-hlPCYWJv5Q8JUtJNUb3cOEbMJPwIbCinQT0gfX96TFY1hpdxAyt7by8OKcJb8lohYcxY24z4sMtg&expires=1777301498499&clientType=3&id=3031239630&userId=186428021	2026-03-28	Счет на оплату аренды 04.2026.xlsx
117	8	https://fd.oneme.ru/getfile?sig=jbRc4elgcTglbfXxb7ecjGmX-56KhkM-TQ4uPKNqher7mZNiN4VFHByL1_lsPyQqIbWp3vF8o7iVm6x_-5qAIg&expires=1777304784399&clientType=3&id=3036248939&userId=186428021	2026-03-28	Счет Февраль 2026.docx
118	9	https://fd.oneme.ru/getfile?sig=9u0fFuPdQmMdh_Z2mZIBAvfUW-ibZVQleTNMLUvENt0h2EsA_81-RNnGOw845koS2Azz2AVRCtxrPpGah_m7fw&expires=1777304789952&clientType=3&id=3043774338&userId=186428021	2026-03-28	Счет Февраль 2026.docx
119	9	https://fd.oneme.ru/getfile?sig=YZfRGBhmX6VLoWV3oSSLYblHo76LG5Gub1DL83c3o4PFXxHlwONSruB7qaYhqVXYWOizZ1A3I43yJEyXxtqeIQ&expires=1777304795622&clientType=3&id=3025528233&userId=186428021	2026-03-28	Счет Февраль 2026.docx
120	8	https://fd.oneme.ru/getfile?sig=RF84NYJ5U-l8ednDVrKm6mizZHWgPruA05nL33fAHHEaGn1CgsnrNoEWmwdS7fSlKlKQWfwdbhLyd3JhehIQyw&expires=1777305368196&clientType=3&id=3042878570&userId=186428021	2026-03-28	Счет Февраль 2026.docx
121	9	https://fd.oneme.ru/getfile?sig=ZrBiCr5Ya-TzX7oaZHHl0s10r49azELfehZSrduZXEFn_bOO301q0DSRr7F2uUQduBcwRaWIoBR57kxr2R0PXw&expires=1777305373808&clientType=3&id=3026588700&userId=186428021	2026-03-28	Счет Февраль 2026.docx
122	9	https://fd.oneme.ru/getfile?sig=GYJHnk85o3S6BiRuxT88-L_mB1RPHfrEwFqRjXnyr0VW8FTf72-klzOWRK34Sk_9kI6h9xjwKWYzfx62xP8TwA&expires=1777305380044&clientType=3&id=3027784837&userId=186428021	2026-03-28	Счет Февраль 2026.docx
123	8	https://fd.oneme.ru/getfile?sig=tpWJcNyfWUZ20wzRJ9Mydsy3fLWMXZHe9-rZlmNvYoZ6ML2mwdFSx35H0t-0M2Wy-2HT4Hw6BYGc90IS15CmnQ&expires=1777305752771&clientType=3&id=3033560513&userId=186428021	2026-03-28	Счет Февраль 2026.docx
124	9	https://fd.oneme.ru/getfile?sig=WmjLeqnhNr1u7klpvvc9n9FcDf8hreO5fEuwzFRESVT54gqCKrKejhTzUT88DkTY9gPZRPtR0FCsUy3c2zTCPA&expires=1777305758580&clientType=3&id=3039880742&userId=186428021	2026-03-28	Счет Февраль 2026.docx
125	9	https://fd.oneme.ru/getfile?sig=xzSOfsfSFE2NvR6vE4HOcQQHaclzijlNNEa9FNGcvTqX8dZUtthmXgZSxPaXo_WqCmy_qUkTT7XUE8eUzf2hLg&expires=1777305764717&clientType=3&id=3032324357&userId=186428021	2026-03-28	Счет Февраль 2026.docx
126	8	https://fd.oneme.ru/getfile?sig=Y024g2NTBLQy-cT7EEdSpaORrMhA9OHfomzgmZjngBZNtzqqzYwc98D424_pPBlzAfpyglukYA0jSQoUXUP4GQ&expires=1777305917402&clientType=3&id=3039247837&userId=186428021	2026-03-28	Счет Февраль 2026.docx
127	8	https://fd.oneme.ru/getfile?sig=70NCizZr5b-BWyOHd4EEnYhAcgyDbzHc7RUzYWgRZWJ7SNAxT_X9qheMAS1IXORpbgTRxa8RJXuxoswTFNHEog&expires=1777305923033&clientType=3&id=3033963507&userId=186428021	2026-03-28	Счет на оплату КУ Февраль 2026.xlsx
128	9	https://fd.oneme.ru/getfile?sig=1PKfk0Syv0MXlrDXcyORqDGhdamXfSbeV1rfVCsbx2vNE_JspcNKD4uuiLNxYX--b8_KZUdNkF18F8V6HiwMHw&expires=1777305949337&clientType=3&id=3037126723&userId=186428021	2026-03-28	Счет Февраль 2026.docx
129	9	https://fd.oneme.ru/getfile?sig=cf_ddiNdOJ34GrW9PGR4xqhDgyqDCAru6yCqAg8YMp-kUPZz3OmA0lGLf2RCME0AMfXiv056WoS4pNsEOpVcyw&expires=1777305955310&clientType=3&id=3028809812&userId=186428021	2026-03-28	Счет Февраль 2026.docx
130	8	https://fd.oneme.ru/getfile?sig=aG-o7rgv8w6CDdnUobUuBi7H8xN2xbKtmT1GKVasN4u2wv3DFylBf9nTlZjCqXabKl4Q58zFkVfIXWfJbdW2ug&expires=1777306032299&clientType=3&id=3026623540&userId=186428021	2026-03-28	Счет Февраль 2026.docx
131	8	https://fd.oneme.ru/getfile?sig=1D5OrKH3IZ5RHqH9wIXm5uVrqJzzixltZsTF2w6tC5lOnRhqsFVQOuxqT356XGaN1eCXLVoe4tHkodcM6Dz_gw&expires=1777306037791&clientType=3&id=3044311438&userId=186428021	2026-03-28	Счет на оплату КУ Февраль 2026.xlsx
132	9	https://fd.oneme.ru/getfile?sig=xM61L1-RPXjbIGp0xlPojTaLWKNUHeWyqvKhLu8zbqlNGme1hCU-HUa-NCeazXGDkzEO77X-v_uEXDE2Lsx3yA&expires=1777306053668&clientType=3&id=3025160427&userId=186428021	2026-03-28	Счет Февраль 2026.docx
133	9	https://fd.oneme.ru/getfile?sig=nTpq01lVI-A3j4Mrxw5S2frmgc-wUotOx2LNu3SUHVcQNthVIc5gRddKFR2LV_Uau_AsKJ9a-mY1AlQtdQPO_Q&expires=1777306059517&clientType=3&id=3024465911&userId=186428021	2026-03-28	Счет Февраль 2026.docx
134	8	https://fd.oneme.ru/getfile?sig=KVboEloItCMxKGQaoDGTIYfSA215Gq3suFe_gmXA48OLPusHtZW3ToKCmWxd_o8AMvaO_iEpQqxQdTB9k-dkZA&expires=1777306454392&clientType=3&id=3033875737&userId=186428021	2026-03-28	Счет Февраль 2026.docx
135	8	https://fd.oneme.ru/getfile?sig=NzDPWafTbnXtkqvtGn9tOPtFQs1jnyGIEYSEIFwAQBIuXrgEd-VHGsqiLMvpfc8PD69C-rEAscgOg_4P1L9VIg&expires=1777306460027&clientType=3&id=3039543074&userId=186428021	2026-03-28	Счет на оплату КУ Февраль 2026.xlsx
136	8	https://fd.oneme.ru/getfile?sig=M078ADQj-_FsjN6qR6pBktiVa6s9UUJovdeWJpf-exIufhshorUxpwxm6FYPR3BVwsMnjw0b8-pB0c0fVo9XKw&expires=1777322206857&clientType=3&id=3040202705&userId=186428021	2026-03-28	Акт расчета КУ ИП Февраль 2026.docx
137	8	https://fd.oneme.ru/getfile?sig=e3K6Y6pyse_hkUTV0uC5UkmD2qAumd_2z0tU9sEAY_KDn7E6RAEMYxrbeNPud2o__0V_YrPi1R4wggapwIrwow&expires=1777322211434&clientType=3&id=3041175470&userId=186428021	2026-03-28	Счет на оплату КУ Февраль 2026.xlsx
138	10	https://fd.oneme.ru/getfile?sig=xtJ4pzpbyEXOMT1s5cDe9CAL-Pnr-iFzz0jgQg3qLbf4znBCGnooLK4-BgzN0vpeLncFHQ35xmBq4GTq0XB5RA&expires=1777322216390&clientType=3&id=3038993458&userId=186428021	2026-03-28	Акт расчета КУ ООО Февраль 2026.docx
139	10	https://fd.oneme.ru/getfile?sig=W3119II4ubxdBL_-p0YizOI3oT9Vee9SSyqnu6lvGTt1zqjXoblo6A02JcnSU2wPTCYREDWUr44M9A9GAz_qSQ&expires=1777322220974&clientType=3&id=3035149543&userId=186428021	2026-03-28	Счет на оплату КУ Февраль 2026.xlsx
140	8	https://fd.oneme.ru/getfile?sig=hakXra_zdZeImYzdVGP6dQc3AoRo3Ak7Kz5351UYgvYHdRgffR4lz8Qdua1gTdZAQhB1z9R3J_-kG2WrkaadYg&expires=1777323266511&clientType=3&id=3034516775&userId=186428021	2026-03-28	Акт расчета КУ ИП Февраль 2026.docx
141	8	https://fd.oneme.ru/getfile?sig=tkrYqLNUgy3c0cVTVZNOD8c_xLjYF-PtPT6KSlMQdeqAOfKqkZbrLof6do8hsRndveT76skwOFD3MiQnz3xk2Q&expires=1777323271332&clientType=3&id=3037289957&userId=186428021	2026-03-28	Счет на оплату КУ Февраль 2026.xlsx
142	10	https://fd.oneme.ru/getfile?sig=ahTRr3cYlsiSUqEAg6GZ8pgfh62H_6xQ9VmDAC-jbPG9HaJ18qS2a4ZjnW099W-xdKnZWY_150fI0O7nb5B6sw&expires=1777323276344&clientType=3&id=3030333859&userId=186428021	2026-03-28	Акт расчета КУ ООО Февраль 2026.docx
143	10	https://fd.oneme.ru/getfile?sig=OmFZTfonyIyo1zmUI8I7cx3c85zAyIvS6K0o-SA12H-bay4UELvylR9Y6sAbjVcNhJiftIiplxvm00pf56UyaA&expires=1777323280915&clientType=3&id=3044910210&userId=186428021	2026-03-28	Счет на оплату КУ Февраль 2026.xlsx
144	8	https://fd.oneme.ru/getfile?sig=hQXfjDGpOsT4EiD_BlcQqo0p3XDrjPPoC_ye2gUavs-fuXNfe8gLsDLYi5G6Mt4r7fqhVNCRsUNdLbaeywwTiQ&expires=1777323379536&clientType=3&id=3029023648&userId=186428021	2026-03-28	Акт расчета КУ ИП Февраль 2026.docx
145	8	https://fd.oneme.ru/getfile?sig=saNNYxIqqDrrlm3AdxzGyqEEEZR4v_rxejShw2gUzwRLMVRmf-3gKWzMvErI_z9HFYbFJ2fQu1CvXCXQjKSuGw&expires=1777323384161&clientType=3&id=3038156672&userId=186428021	2026-03-28	Счет на оплату КУ Февраль 2026.xlsx
146	10	https://fd.oneme.ru/getfile?sig=zdshEswTuvwsG0okcBdoi3CC3-FUvzLykZ8pjtXkSAPZNNVTxqMv458nPby5uu7wBHn21gjWIG9Ck_yCkcIOqQ&expires=1777323389162&clientType=3&id=3044022902&userId=186428021	2026-03-28	Акт расчета КУ ООО Февраль 2026.docx
147	10	https://fd.oneme.ru/getfile?sig=vgdrDSIt5PqDfjLM9tqsA476vnCHwpVbj23NA1wMP04APLKcvlR6spzhEtWlNUcgbvQoxPmRPPD8rug4lfyerA&expires=1777323393756&clientType=3&id=3037493594&userId=186428021	2026-03-28	Счет на оплату КУ Февраль 2026.xlsx
148	10	https://fd.oneme.ru/getfile?sig=Cx9HJr9Dlm4pgtQpDlLy_xfEZQe6SutnfShYg3tuh-uTofMaRmdBRpZ_jFjrvUXtQl_hhckWetv2nuC3XPDeTA&expires=1777325984629&clientType=3&id=3034538177&userId=186428021	2026-03-29	Акт расчета КУ ООО Февраль 2026.docx
149	10	https://fd.oneme.ru/getfile?sig=37zb83y4Ty5MR3FB2P6dKgsozfD0mySrwbmmUxxvUst6RKINBnzkFNkns3gXbEZr5-lk73arRkVKtc7tOoi3aQ&expires=1777325990034&clientType=3&id=3047131662&userId=186428021	2026-03-29	Счет на оплату КУ Февраль 2026.xlsx
150	8	https://fd.oneme.ru/getfile?sig=Qu8UI8gzQFiIa_4pc77GPQVQaa6l2Vx5txE1lIy55QgDv6QU18IuHp-EzL-cNC-oE2XseOPIyAEFrEmpi0CyOw&expires=1777325995700&clientType=3&id=3033010790&userId=186428021	2026-03-29	Акт расчета КУ ИП Февраль 2026.docx
151	10	https://fd.oneme.ru/getfile?sig=xvgTHtgoeZRYQWicPGvjW_vrftVBKShZVSY-Vk9rR1BNoTYk3MK79LeaRaHeT6MyZYnNv0qPx4fhvpOmf9r6qQ&expires=1777326209702&clientType=3&id=3036400832&userId=186428021	2026-03-29	Акт расчета КУ ООО Февраль 2026.docx
152	10	https://fd.oneme.ru/getfile?sig=xbiVms0_Mp3GA31ZECYEW1OSF9qQ4Gp1NId-QbrtDG3r3FZlZWaBt_QXfHN10PBE3dAWRQONcC0SE3vo5U00GA&expires=1777326215136&clientType=3&id=3028329849&userId=186428021	2026-03-29	Счет на оплату КУ Февраль 2026.xlsx
153	8	https://fd.oneme.ru/getfile?sig=o4tK8Z2jlWoZBzrgCXCcCVSQX0OiYdIfh2Io-qXhriORpOOUpfKtg-uTyevkr7Sv2OljCXuaZsOe-FzGdJY15Q&expires=1777326220941&clientType=3&id=3037961520&userId=186428021	2026-03-29	Акт расчета КУ ИП Февраль 2026.docx
154	8	https://fd.oneme.ru/getfile?sig=hKKtZegheLEejt23t3taQ2BuF49OcTa8oB5p-nwdYsMzSqjitLqwB3TaVo3a85YU2DWrJzKPqMUDHSNlHWAfRg&expires=1777326226103&clientType=3&id=3041216032&userId=186428021	2026-03-29	Счет на оплату КУ Февраль 2026.xlsx
155	8	https://fd.oneme.ru/getfile?sig=192of9RbBSpiFWoKj1tMYtDzOwPLqyaP0jChwaVfzHCtKvQQmiuLgTe3YBL9nXLMlkztlXgVq3046hKo2Yfuyg&expires=1777327149303&clientType=3&id=3034404389&userId=186428021	2026-03-29	Акт расчета КУ ИП Февраль 2026.docx
156	8	https://fd.oneme.ru/getfile?sig=iPE9dXuQkZGBqQtmRD29V4ftGAnabe5zpFL3gI66_hc62Q5AL6llmuZlnqYMNKLnKejlZktFBrN7nPAOLmYfOQ&expires=1777327153975&clientType=3&id=3041674810&userId=186428021	2026-03-29	Счет на оплату КУ Февраль 2026.xlsx
157	10	https://fd.oneme.ru/getfile?sig=e-YzvI_gt5uxOkQ77s1INNrQCzNHgpIIjQhQ_OaBDW3sHVqAWEtqc4tmhZ1TWXhZzaCR-dCh1DeuPIjzYgAmOQ&expires=1777327159117&clientType=3&id=3033327543&userId=186428021	2026-03-29	Акт расчета КУ ООО Февраль 2026.docx
158	10	https://fd.oneme.ru/getfile?sig=UL6byDOmHCgBMNHT8NcQtNvD1FOTR36VBG7P2CjOQayZmeIobSDfOtEb5qsOWi7YfKEy5JRP-YTn5QHWzrT4lQ&expires=1777327163700&clientType=3&id=3028575100&userId=186428021	2026-03-29	Счет на оплату КУ Февраль 2026.xlsx
159	8	https://fd.oneme.ru/getfile?sig=XX-1U5d3S1MkfuXi6L3WFw_50P5gVUS7Av1GNDT2Aaa1Y4HO5YyLvVcmp8PX8bNvGOfdoiKqKUwsxOQI3ja9GA&expires=1777396537877&clientType=3&id=3039080423&userId=186428021	2026-03-29	Акт расчета КУ ИП Февраль 2026.docx
160	8	https://fd.oneme.ru/getfile?sig=F6WFcEyHEc9Bg2OqykOpUTomwTO1sDxll243HDf2mbT4tHolRWZHd6_cbdB4LzExzth5LJu8fcCD9HgzJEqRWQ&expires=1777396544655&clientType=3&id=3040308629&userId=186428021	2026-03-29	Счет на оплату КУ Февраль 2026.xlsx
161	10	https://fd.oneme.ru/getfile?sig=DB_zxT1UeitEkoPq3voVXz8SA7KznIK3hs-ju8IlkRUwmqRMJ_J4y_1nziAKibwvC4EV_gvBBxXQPxC4Ea0lrw&expires=1777396554279&clientType=3&id=3036845926&userId=186428021	2026-03-29	Акт расчета КУ ООО Февраль 2026.docx
162	10	https://fd.oneme.ru/getfile?sig=oQhwCEx7UIJFHXnSPZ3L4DL7Jl62NcENSKtdWjVE0g4oHhFHI0vCTO8IXmhUrTTyaq9VxWGgO4gq-SkQxHCumg&expires=1777396560053&clientType=3&id=3036679375&userId=186428021	2026-03-29	Счет на оплату КУ Февраль 2026.xlsx
163	9	https://fd.oneme.ru/getfile?sig=zel_vT0C5DrJ0NNm5wxCOukoITJi0luVU9U2ES6IGgVomtMLPoXXGdfeq_qCWOTH9O46dwCVCTgCacZNZudWew&expires=1777410131255&clientType=3&id=3038144461&userId=186428021	2026-03-30	Счет на оплату аренды 04.2026.xlsx
164	9	https://fd.oneme.ru/getfile?sig=OWuB8MufpCKVqDVZFYFSrxLBOBEUhPIhZRZH0vFIQnqcVM3KPFwqVQQFG47rYuZo-oIFTie3EubpozPAR-qfHg&expires=1777410134046&clientType=3&id=3032216713&userId=186428021	2026-03-30	Акт 03.2026.xlsx
165	8	https://fd.oneme.ru/getfile?sig=1GT3Ci7JtaapRYGVvvHHnvpQOGEKPG90_tZFrennPF3jjbYCjoyZlejDmX4Iu7kikHSxVfo-yPR9pcjq7s0A6w&expires=1777410137276&clientType=3&id=3032198684&userId=186428021	2026-03-30	Счет на оплату аренды 04.2026.xlsx
166	8	https://fd.oneme.ru/getfile?sig=h-Y1xqd0TfwLBtMHLGeT-FNo5boYg_2_Pk0dQtBcGEeF8VtlBdpHLRrYPxcwWofqBVnKUnVdoNouAvkGuaIkiQ&expires=1777410139946&clientType=3&id=3043445694&userId=186428021	2026-03-30	Акт 03.2026.xlsx
167	8	https://fd.oneme.ru/getfile?sig=G_brMN1sp_Aa9eVXZqGSILjSGBs2nmhGGsl49M2x7KhaEB0HMMsxq2CgYW-7woiaUYi7FBWOMK_bCMemchg6Bw&expires=1777410142783&clientType=3&id=3046265973&userId=186428021	2026-03-30	Акт №9 КУ март 2026.xlsx
168	9	https://fd.oneme.ru/getfile?sig=6O_Lq8zh1Zz99uguEiRq4_YsC02tCViIjQkAR6DEREMeU8qokMuHoFw1xreoPlFZ8YasuLENhlSlhyFFv5tGqA&expires=1777410145813&clientType=3&id=3035101066&userId=186428021	2026-03-30	Счет на оплату аренды 04.2026.xlsx
169	9	https://fd.oneme.ru/getfile?sig=fgrTWupeU9b4gr8M0MCVm9ChglcK1-QDC_jiNoIduirOOBebMr6RxFLmW1xDHzIKi3Zg8eesswVo3XbQNvcWgQ&expires=1777410148479&clientType=3&id=3040305663&userId=186428021	2026-03-30	Акт 03.2026.xlsx
170	9	https://fd.oneme.ru/getfile?sig=MC2c8xEtAl6ewfBnSIP0Q_73THGey-NGvhQD61kBsqHd8ke3R_nwUud69DPU0a7xAbLxCjE6DZSJBtETK1M3sA&expires=1777410470997&clientType=3&id=3032163124&userId=186428021	2026-03-30	Счет на оплату аренды 04.2026.xlsx
171	9	https://fd.oneme.ru/getfile?sig=oUanQSZNDtuYjP8LWrNiQGPyX2B8oq-q6rEIDw_Ci0yvcCySB69RK5QwtOfp-sAnzEPYgvRhLgnnIpzWs4S1yg&expires=1777410473401&clientType=3&id=3045708310&userId=186428021	2026-03-30	Акт 03.2026.xlsx
172	8	https://fd.oneme.ru/getfile?sig=nIbE-lvfWO_smZvgD3Rm7avCPtTS0k6agMYJ739QxopaP-pnmxFsj9mbOotOSQGBb0jXuf2kcoPU_TCSvt1O4A&expires=1777410476462&clientType=3&id=3046303506&userId=186428021	2026-03-30	Счет на оплату аренды 04.2026.xlsx
173	8	https://fd.oneme.ru/getfile?sig=AORtgcHinbl6FX8mKd_DdDacc-omltAREowlKwkr54a1QUH_ZyyQm8JU_xxYMTcoy0_RK3Zed5XQtjb7_qRXtQ&expires=1777410478814&clientType=3&id=3042015587&userId=186428021	2026-03-30	Акт 03.2026.xlsx
174	8	https://fd.oneme.ru/getfile?sig=Z-ARZsnxOUawRFZu60Ra2Psvi6y-v1qiXo7a7rZFXzrXs3AANel1f5xbNR2jQVZSBsBwIixjIi2WkiFhCcZUfA&expires=1777410481224&clientType=3&id=3037419471&userId=186428021	2026-03-30	Акт №10 КУ март 2026.xlsx
175	9	https://fd.oneme.ru/getfile?sig=uZErocciFUEbVCWnFISLn5mlbcuRdqe7JQAxQ8r5OlHErux1JlBuamy3U3kXh22mA1o83G0OOkSZhAj_ZNjjhg&expires=1777410484117&clientType=3&id=3044885756&userId=186428021	2026-03-30	Счет на оплату аренды 04.2026.xlsx
176	9	https://fd.oneme.ru/getfile?sig=UK2ObMLKqOpC48RZp2g8x-OpAKF48Lg8Q56euzqX_UMIp8N9dJrjSNp1IbxyZ0_LaPaJfvjHSW9Zevi-E8hajg&expires=1777410486513&clientType=3&id=3034156116&userId=186428021	2026-03-30	Акт 03.2026.xlsx
\.


--
-- Data for Name: bussines; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.bussines (id, name_company, id_form, square, bid, acceptance_certificate, agreement, state_company, id_type_of_activity, end_date_agreement, sheet_name, surname, first_name, patronymic, number_act, phone, number_act_ku, director_title) FROM stdin;
11	Атлант-Поволжье	1	61	115000.00	2026-01-16	№18	\N	18	16.12.2026	K61.0	Казанцев	Антон	Александрович	1	89872969704	0	Директор
10	Компания Экосервис	1	52	115000.00	2026-02-04	17	\N	16	20.09.2026	K52.0	Колоколов	Роман	Владимирович	1	899999999	7	Генеральный директор
9	АТЛАНТ-Т	1	27.8	50000.00	2025-04-04	№13	\N	14	21.01.2027	K27.8	Казанцев	Антон	Александрович	65	89872969704	0	Генеральный директор
8	Хасанова Лейсан Маратовна	2	20.5	71750.00	2026-03-12	№20	\N	13	12.02.2027	K20.5	Хасанова	Лейсан	Маратовна	51	879534887032	10	\N
\.


--
-- Data for Name: form_of_doing_business; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.form_of_doing_business (id, name) FROM stdin;
1	ООО
2	ИП
3	Самозанятость
4	АО
5	ЗАО
6	Товарищество
7	Кооператив
\.


--
-- Data for Name: type_counter; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.type_counter (id, name) FROM stdin;
1	Холодная вода
2	Электричество
3	Горячая вода
\.


--
-- Data for Name: type_of_activity; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.type_of_activity (id, name) FROM stdin;
1	Панели
2	ОкнаО
3	Окнао
4	АРИТ
5	Арит
6	Парусы
7	СВЕТ
8	СВЕТА
9	Света
10	НАЙМ
11	Найм
12	345678
13	Кофейня
14	офис,холодильники
15	Офис,Холодильники
16	магазин
17	Магазин
18	холодильники
19	Холодильники
\.


--
-- Data for Name: us_readings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.us_readings (id, number_counter, counter_type_id, business_id) FROM stdin;
23	54934245	1	8
24	54934401	3	8
25	111	2	8
26	123	1	10
27	123	3	10
28	123	2	10
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (user_id, first_name, second_name, patronymic, id_business, phone_number, sheets_name, username) FROM stdin;
109821500	\N	\N	\N	9	\N	K27.8	
262267428	\N	\N	\N	9	\N	K27.8	
87411656	\N	\N	\N	8	\N	K20.5	
\.


--
-- Name: business_documents_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.business_documents_id_seq', 176, true);


--
-- Name: bussines_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.bussines_id_seq', 11, true);


--
-- Name: form_of_doing_business_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.form_of_doing_business_id_seq', 7, true);


--
-- Name: type_counter_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.type_counter_id_seq', 3, true);


--
-- Name: type_of_activity_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.type_of_activity_id_seq', 19, true);


--
-- Name: us_readings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.us_readings_id_seq', 31, true);


--
-- Name: bot_drafts bot_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_drafts
    ADD CONSTRAINT bot_drafts_pkey PRIMARY KEY (draft_key);


--
-- Name: business_documents business_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_documents
    ADD CONSTRAINT business_documents_pkey PRIMARY KEY (id);


--
-- Name: bussines bussines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bussines
    ADD CONSTRAINT bussines_pkey PRIMARY KEY (id);


--
-- Name: form_of_doing_business form_of_doing_business_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.form_of_doing_business
    ADD CONSTRAINT form_of_doing_business_pkey PRIMARY KEY (id);


--
-- Name: type_of_activity name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.type_of_activity
    ADD CONSTRAINT name UNIQUE (name);


--
-- Name: type_counter type_counter_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.type_counter
    ADD CONSTRAINT type_counter_pkey PRIMARY KEY (id);


--
-- Name: type_of_activity type_of_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.type_of_activity
    ADD CONSTRAINT type_of_activity_pkey PRIMARY KEY (id);


--
-- Name: us_readings us_readings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.us_readings
    ADD CONSTRAINT us_readings_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: idx_bot_drafts_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bot_drafts_updated_at ON public.bot_drafts USING btree (updated_at);


--
-- Name: business_documents business_documents_id_business_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_documents
    ADD CONSTRAINT business_documents_id_business_fkey FOREIGN KEY (id_business) REFERENCES public.bussines(id);


--
-- Name: bussines bussines_id_form_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bussines
    ADD CONSTRAINT bussines_id_form_fkey FOREIGN KEY (id_form) REFERENCES public.form_of_doing_business(id);


--
-- Name: bussines bussines_id_type_of_activity_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bussines
    ADD CONSTRAINT bussines_id_type_of_activity_fkey FOREIGN KEY (id_type_of_activity) REFERENCES public.type_of_activity(id);


--
-- Name: us_readings us_readings_business_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.us_readings
    ADD CONSTRAINT us_readings_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.bussines(id);


--
-- Name: us_readings us_readings_counter_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.us_readings
    ADD CONSTRAINT us_readings_counter_type_id_fkey FOREIGN KEY (counter_type_id) REFERENCES public.type_counter(id);


--
-- Name: users users_id_business_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_id_business_fkey FOREIGN KEY (id_business) REFERENCES public.bussines(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict vayriHEP0f6jOsRUpyYS7fBe8R9okzW3geqrUyughllSBgUOyMZjc5gFCDt7jaF


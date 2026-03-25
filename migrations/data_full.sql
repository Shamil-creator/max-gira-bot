--
-- PostgreSQL database dump
--

\restrict 5KXEAvIDW1lb9RfpS5JnP4of1SASy2dAN7dFaxSEBJ2BboyHZw3fNr7hkfojDGS

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

--
-- Data for Name: bot_drafts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.bot_drafts (draft_key, scalar_value, list_value, updated_at) FROM stdin;
user:237593021:list_cold_water	\N	["12"]	2026-03-22 22:47:53.121164+03
admin_access:237593021	1	\N	2026-03-24 11:27:32.214415+03
user:87411656:meters	hw,cw,el	\N	2026-03-24 22:27:28.770746+03
admin_access:79513681	1	\N	2026-03-24 22:51:47.793234+03
user:109821500:meters	hw,cw,el	\N	2026-03-25 01:16:42.341533+03
admin_access:228004937	1	\N	2026-03-25 17:16:56.49646+03
user:262267428:meters	hw,cw,el	\N	2026-03-25 18:05:29.078667+03
\.


--
-- Data for Name: form_of_doing_business; Type: TABLE DATA; Schema: public; Owner: postgres
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
-- Data for Name: type_of_activity; Type: TABLE DATA; Schema: public; Owner: postgres
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
\.


--
-- Data for Name: bussines; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.bussines (id, name_company, id_form, square, bid, acceptance_certificate, agreement, state_company, id_type_of_activity, end_date_agreement, sheet_name, surname, first_name, patronymic, number_act) FROM stdin;
7	НАЙМ	2	456	45000.00	2025-12-12	45	\N	10	12.12.2026	K456.0	НАЙМ	НАЙМ	НАЙМ	4
\.


--
-- Data for Name: business_documents; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.business_documents (id, id_business, file_id, date_added) FROM stdin;
12	7	https://fd.oneme.ru/getfile?sig=8k0jfO5VyKFtPMJfdjrD9FUOS5TPaxh3LJU7vQhGZZxtjqAalAQPq07yOTSsffa66OMD9ZaoHwYfNYd1s3HZFQ&expires=1777044385800&clientType=3&id=2997036755&userId=186428021	2026-03-25
13	7	https://fd.oneme.ru/getfile?sig=jU33MZin17NFeCypl12vR59vkWMp1n7aFH7MLZnXWCDColF-FOCPLD8cTaX923yyV8oJUdfsINzIgAYwvbGT5w&expires=1777045270148&clientType=3&id=3006497206&userId=186428021	2026-03-25
14	7	https://fd.oneme.ru/getfile?sig=ll25wl1vfqgemXYLKJ5q740dEqyVupXTwl7lM7icPHBy9i8fprNr-Ia_SSOjGItrYdP19zBCPuhhVXmRa1FT_A&expires=1777058634195&clientType=3&id=3013938970&userId=186428021	2026-03-25
15	7	https://fd.oneme.ru/getfile?sig=enHiwsiMA7wEhu9TJnRaaJNzuAQaNVk11ImT4EF8gIRqKRleuq6pZcn-Ws9R_LYQqQx3WXRYqpvwX4hR0uV90w&expires=1777058937660&clientType=3&id=3008363916&userId=186428021	2026-03-25
16	7	https://fd.oneme.ru/getfile?sig=xoO00_pSRbXmhyE1b7u_fcdrJX124hN78CCcHl5w7doV1L20wHFWPjYsnQhwK81i4DLJzB9R_QtFTJOa14cdsA&expires=1777060584585&clientType=3&id=3013050985&userId=186428021	2026-03-25
17	7	https://fd.oneme.ru/getfile?sig=NDIiDU5SKDlltfTGp1qfGa88qPcYYsLtc60KlTdrD_5cXxnFqyiWc74rl_wmwdUfyIzOF2LtKW-GHQ4h5iHHSw&expires=1777060986589&clientType=3&id=3002902472&userId=186428021	2026-03-25
18	7	https://fd.oneme.ru/getfile?sig=BC9WzHa4la8SSe5x9cjzcFIt2XEobt447U7iOeAjO4dUEV-1JnYxRsKewAnLAg2t8Yu31kXmXNq8__EZKYwJmw&expires=1777061377691&clientType=3&id=3014654447&userId=186428021	2026-03-25
19	7	https://fd.oneme.ru/getfile?sig=BWD8lDPnOLARcQ0kghuZY-p9g9CjzL7a5D29fnMsiXHNw-EBWBNQixfN1KYEnvTrxNfY3_RJY-rccMLOP6VEHQ&expires=1777061847254&clientType=3&id=3009037055&userId=186428021	2026-03-25
20	7	https://fd.oneme.ru/getfile?sig=Nna5uL4dK5Xn-nJ4b5Qaup9v_b_UDJDM4ayY1BfMtvmvt8X7X1YXDIqNAg18j-eJcqJS3diEgK1Bs9FaDLhd5w&expires=1777062660036&clientType=3&id=3009997554&userId=186428021	2026-03-25
21	7	https://fd.oneme.ru/getfile?sig=gRk637mm9k_BrXmdfdQzVr1D8iU25iMo6pzB2VNQwg7C7hab2s5gjWW4DyRY11INtakMtmeEeNGSXAYNAtN2NQ&expires=1777062989637&clientType=3&id=3003056240&userId=186428021	2026-03-25
22	7	https://fd.oneme.ru/getfile?sig=xewxLW_FhsU5Pyu-IWHVTeGojG8mwUdRmBcDG0Ko_eUrDMylUwqEhjxH6qBSG4uGd8On9AKGktQUDLLHUyPR1g&expires=1777063531420&clientType=3&id=3012487895&userId=186428021	2026-03-25
23	7	https://fd.oneme.ru/getfile?sig=EJNah15vK612E-bHVkvb2losMZH_JzQmo-T3peRC6U7bXVWpxOEwUfmUPIzDj0_g5HNeZfqLGR9PFDZV8_9-ww&expires=1777063977972&clientType=3&id=3011177559&userId=186428021	2026-03-25
24	7	https://fd.oneme.ru/getfile?sig=QZbRkGFk00n1ClJ1gQC6TCq69-7XcKS_K74pOzAlAD2D4-w_ToJYFjnk8YxmwJqC3noYZVXvBCDCScJP3d-fMQ&expires=1777064374629&clientType=3&id=3007259992&userId=186428021	2026-03-25
25	7	https://fd.oneme.ru/getfile?sig=3xHQdi-OJZTpMaw2fyCOM_Os-lniDbAASTy-sT9vlTHkccNBFD0GegoPf8AkgsDSk04O0sBfdw4uS-DCFwHtXA&expires=1777064679552&clientType=3&id=3002164149&userId=186428021	2026-03-26
26	7	https://fd.oneme.ru/getfile?sig=Ug1T706dlYtiWlTDrik0vgCNmt-dMdzWkGfnz1jkdDRQPmO-yXQ1YQGQuAgbDWI79jvNoQ-i_qUu6Th_PnzEog&expires=1777064762601&clientType=3&id=3014742024&userId=186428021	2026-03-26
27	7	https://fd.oneme.ru/getfile?sig=DqehXvqryk_849VYKVKXt35Ws2BqpZ7joplv7xI_WcAleHtMlXesbTz-L7Zw0lN09VLh7q9l6NTEAdfL9DI2PA&expires=1777064822528&clientType=3&id=3009648667&userId=186428021	2026-03-26
28	7	https://fd.oneme.ru/getfile?sig=W2OaQhtNAStZxK5TpdvwkxI3vsKx0dOxXWSuu-snb8uI1_qPDklLPN27UlYLHn8Ah0PuL1eMq8wYMnz4S4uKiQ&expires=1777065041087&clientType=3&id=3007717401&userId=186428021	2026-03-26
29	7	https://fd.oneme.ru/getfile?sig=3qrnV0_tbARQq3iP6J0IW-O5_4iLYc9CjAknZx2UkAM6Vg8S6oku78OcuPfi60HGysGRuGIfqc5Fyk9JVsfePA&expires=1777065360607&clientType=3&id=3013662254&userId=186428021	2026-03-26
30	7	https://fd.oneme.ru/getfile?sig=DAB6BNZEdFZXZTvRmLP9B4gF_xLABhOc5fMsYDP3T06aYRjEZN3IS9vcLEz0IZ9nPvvUaMe5DhsKru_f6u5a8A&expires=1777065673596&clientType=3&id=3013555647&userId=186428021	2026-03-26
31	7	https://fd.oneme.ru/getfile?sig=YVMYaXd7QJYxlZQ_sUfYU79tmSu7tyeBpuR_8B8xUIL_5dEBDtSARMn5KXwQoVDEzocFmoCeoUYWfAuLzFUIhg&expires=1777065838011&clientType=3&id=3014331181&userId=186428021	2026-03-26
32	7	https://fd.oneme.ru/getfile?sig=gcJ5QRvp6rONugzSFVfZBS2vPU0bCJwndfeuyGWtcPgojIlF6A1cznceDdyFVJ6aP9AMdc973_0LQcJ7CuCgwA&expires=1777065964917&clientType=3&id=3007378091&userId=186428021	2026-03-26
33	7	https://fd.oneme.ru/getfile?sig=bQ_j3xRE2M9E4TNy-Sw4CZv6L9SOf1uOklIZ6ZLlLGH91_9JE8s8gOVQJCcqwl-_zMn-5XEQu8P1tPHxPp9ncA&expires=1777070476763&clientType=3&id=3010751519&userId=186428021	2026-03-26
34	7	https://fd.oneme.ru/getfile?sig=K-_ulkWVXG9dZO4oBSwyBxKK0z2dDekvg7oCzNqxyR4KA5g8ZEHjGOvQ-RkxBuKtOh9LAMoJKo7Mz66SMpA5ZA&expires=1777070865795&clientType=3&id=3008084929&userId=186428021	2026-03-26
35	7	https://fd.oneme.ru/getfile?sig=YpC_92n1NnesZ9scqEtYd7F0ZTFGeNi7SU_9dpXCQnTyP-fZvZYFsDI-wMC8dDDuN5ca-TLi4ibQoUen6Xa4mQ&expires=1777071743622&clientType=3&id=3006815940&userId=186428021	2026-03-26
\.


--
-- Data for Name: type_counter; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.type_counter (id, name) FROM stdin;
1	Холодная вода
2	Электричество
3	Горячая вода
\.


--
-- Data for Name: us_readings; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.us_readings (id, number_counter, counter_type_id, business_id) FROM stdin;
20	213	1	7
21	212	3	7
22	211	2	7
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (user_id, first_name, second_name, patronymic, id_business, phone_number, sheets_name, username) FROM stdin;
262267428	\N	\N	\N	7	\N	K456.0	\N
\.


--
-- Name: business_documents_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.business_documents_id_seq', 35, true);


--
-- Name: bussines_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.bussines_id_seq', 7, true);


--
-- Name: form_of_doing_business_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.form_of_doing_business_id_seq', 7, true);


--
-- Name: type_counter_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.type_counter_id_seq', 3, true);


--
-- Name: type_of_activity_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.type_of_activity_id_seq', 11, true);


--
-- Name: us_readings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.us_readings_id_seq', 22, true);


--
-- PostgreSQL database dump complete
--

\unrestrict 5KXEAvIDW1lb9RfpS5JnP4of1SASy2dAN7dFaxSEBJ2BboyHZw3fNr7hkfojDGS


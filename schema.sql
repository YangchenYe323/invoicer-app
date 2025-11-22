--
-- PostgreSQL database dump
--

\restrict NM0LqJUdlxd1D28EpUDPyF72YJ2NKdrsWcvUS4t7H0qCerSV3nuZYuGHQME0Y6e

-- Dumped from database version 18.0 (902cc69)
-- Dumped by pg_dump version 18.1 (Ubuntu 18.1-1.pgdg24.04+2)

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

--
-- Name: drizzle; Type: SCHEMA; Schema: -; Owner: neondb_owner
--

CREATE SCHEMA drizzle;


ALTER SCHEMA drizzle OWNER TO neondb_owner;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: __drizzle_migrations; Type: TABLE; Schema: drizzle; Owner: neondb_owner
--

CREATE TABLE drizzle.__drizzle_migrations (
    id integer NOT NULL,
    hash text NOT NULL,
    created_at bigint
);


ALTER TABLE drizzle.__drizzle_migrations OWNER TO neondb_owner;

--
-- Name: __drizzle_migrations_id_seq; Type: SEQUENCE; Schema: drizzle; Owner: neondb_owner
--

CREATE SEQUENCE drizzle.__drizzle_migrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE drizzle.__drizzle_migrations_id_seq OWNER TO neondb_owner;

--
-- Name: __drizzle_migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: drizzle; Owner: neondb_owner
--

ALTER SEQUENCE drizzle.__drizzle_migrations_id_seq OWNED BY drizzle.__drizzle_migrations.id;


--
-- Name: account; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.account (
    id text NOT NULL,
    account_id text NOT NULL,
    provider_id text NOT NULL,
    user_id text NOT NULL,
    access_token text,
    refresh_token text,
    id_token text,
    access_token_expires_at timestamp without time zone,
    refresh_token_expires_at timestamp without time zone,
    scope text,
    password text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.account OWNER TO neondb_owner;

--
-- Name: invoice; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.invoice (
    id integer NOT NULL,
    source_id integer,
    message_id text,
    invoice_number text,
    vendor_name text,
    due_date timestamp with time zone,
    total_amount numeric(10,2),
    currency text,
    payment_status text,
    line_items jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id text NOT NULL,
    attached_files jsonb,
    uid integer
);


ALTER TABLE public.invoice OWNER TO neondb_owner;

--
-- Name: COLUMN invoice.id; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.id IS 'Auto-incrementing integer primary key';


--
-- Name: COLUMN invoice.source_id; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.source_id IS 'The source ID of the source that contains the invoice, foreign key to the source table';


--
-- Name: COLUMN invoice.message_id; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.message_id IS 'The IMAP message ID of the email that contains the invoice, stored as a string';


--
-- Name: COLUMN invoice.invoice_number; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.invoice_number IS 'The invoice or receipt number, stored as a string';


--
-- Name: COLUMN invoice.vendor_name; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.vendor_name IS 'The vendor name, stored as a string';


--
-- Name: COLUMN invoice.due_date; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.due_date IS 'The due date, stored as a date in ISO 8601 format';


--
-- Name: COLUMN invoice.total_amount; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.total_amount IS 'The total amount, stored as a numeric value';


--
-- Name: COLUMN invoice.currency; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.currency IS 'The currency, stored as a string';


--
-- Name: COLUMN invoice.payment_status; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.payment_status IS 'The payment status, stored as a string, e.g., paid, unpaid, pending, etc.';


--
-- Name: COLUMN invoice.line_items; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.line_items IS 'The line items, stored as a JSON array of LineItem objects, each containing a description, quantity, and unit price';


--
-- Name: COLUMN invoice.created_at; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.created_at IS 'The date and time the invoice was created, automatically set to the current timestamp';


--
-- Name: COLUMN invoice.updated_at; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.updated_at IS 'The date and time the invoice was last updated, automatically set to the current timestamp';


--
-- Name: COLUMN invoice.user_id; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.user_id IS 'The user ID of the user who owns the invoice, foreign key to the user table';


--
-- Name: COLUMN invoice.attached_files; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.attached_files IS 'The attached files in the invoice, stored as a JSON array of AttachedFile objects, each containing a file name and S3 object key';


--
-- Name: COLUMN invoice.uid; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.invoice.uid IS 'The IMAP UID of the email that contains the invoice, stored as an integer';


--
-- Name: invoice_id_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

ALTER TABLE public.invoice ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.invoice_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: session; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.session (
    id text NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    token text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    ip_address text,
    user_agent text,
    user_id text NOT NULL
);


ALTER TABLE public.session OWNER TO neondb_owner;

--
-- Name: source; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.source (
    id integer NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id text NOT NULL,
    email_address text NOT NULL,
    source_type text NOT NULL,
    oauth2_access_token text,
    oauth2_refresh_token text,
    oauth2_access_token_expires_at timestamp without time zone,
    oauth2_refresh_token_expires_at timestamp without time zone
);


ALTER TABLE public.source OWNER TO neondb_owner;

--
-- Name: COLUMN source.id; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.id IS 'Auto-incrementing integer primary key';


--
-- Name: COLUMN source.name; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.name IS 'The name of the source, autogenerated via convention <username>/<provider_type>/<email_address>';


--
-- Name: COLUMN source.created_at; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.created_at IS 'The date and time the source was created, automatically set to the current timestamp';


--
-- Name: COLUMN source.updated_at; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.updated_at IS 'The date and time the source was last updated, automatically set to the current timestamp';


--
-- Name: COLUMN source.user_id; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.user_id IS 'The user ID of the user who owns the source, foreign key to the user table';


--
-- Name: COLUMN source.email_address; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.email_address IS 'The email address of the source';


--
-- Name: COLUMN source.source_type; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.source_type IS 'The type of the source, e.g., gmail, outlook, etc.';


--
-- Name: COLUMN source.oauth2_access_token; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.oauth2_access_token IS 'OAuth2 access token, null if the source is not using OAuth2, stored as a string';


--
-- Name: COLUMN source.oauth2_refresh_token; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.oauth2_refresh_token IS 'OAuth2 refresh token, null if the source is not using OAuth2, stored as a string';


--
-- Name: COLUMN source.oauth2_access_token_expires_at; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.oauth2_access_token_expires_at IS 'OAuth2 access token expiration date, null if the source is not using OAuth2, stored as a string in ISO 8601 format';


--
-- Name: COLUMN source.oauth2_refresh_token_expires_at; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source.oauth2_refresh_token_expires_at IS 'OAuth2 refresh token expiration date, null if the source is not using OAuth2, stored as a string in ISO 8601 format';


--
-- Name: source_folder; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.source_folder (
    id integer NOT NULL,
    source_id integer NOT NULL,
    folder_name text NOT NULL,
    uid_validity text NOT NULL,
    high_water_mark integer,
    low_water_mark integer,
    last_processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.source_folder OWNER TO neondb_owner;

--
-- Name: COLUMN source_folder.id; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source_folder.id IS 'Auto-incrementing integer primary key';


--
-- Name: COLUMN source_folder.source_id; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source_folder.source_id IS 'The source ID of the source that contains the folder, foreign key to the source table';


--
-- Name: COLUMN source_folder.folder_name; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source_folder.folder_name IS 'The name of the folder, stored as a string';


--
-- Name: COLUMN source_folder.uid_validity; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source_folder.uid_validity IS 'The UID validity of the folder, stored as a string';


--
-- Name: COLUMN source_folder.high_water_mark; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source_folder.high_water_mark IS 'The largest message UID in the folder that has been processed, stored as an integer, null if haven''t processed any messages yet';


--
-- Name: COLUMN source_folder.low_water_mark; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source_folder.low_water_mark IS 'The smallest message UID in the folder that has been processed, stored as an integer, null if haven''t processed old messages yet';


--
-- Name: COLUMN source_folder.last_processed_at; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source_folder.last_processed_at IS 'The date and time the folder was last processed, stored as a date in ISO 8601 format';


--
-- Name: COLUMN source_folder.created_at; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source_folder.created_at IS 'The date and time the folder was created, stored as a date in ISO 8601 format';


--
-- Name: COLUMN source_folder.updated_at; Type: COMMENT; Schema: public; Owner: neondb_owner
--

COMMENT ON COLUMN public.source_folder.updated_at IS 'The date and time the folder was last updated, stored as a date in ISO 8601 format';


--
-- Name: source_folder_id_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

ALTER TABLE public.source_folder ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.source_folder_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: source_id_seq; Type: SEQUENCE; Schema: public; Owner: neondb_owner
--

ALTER TABLE public.source ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.source_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: user; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public."user" (
    id text NOT NULL,
    name text NOT NULL,
    email text NOT NULL,
    email_verified boolean DEFAULT false NOT NULL,
    image text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public."user" OWNER TO neondb_owner;

--
-- Name: verification; Type: TABLE; Schema: public; Owner: neondb_owner
--

CREATE TABLE public.verification (
    id text NOT NULL,
    identifier text NOT NULL,
    value text NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.verification OWNER TO neondb_owner;

--
-- Name: __drizzle_migrations id; Type: DEFAULT; Schema: drizzle; Owner: neondb_owner
--

ALTER TABLE ONLY drizzle.__drizzle_migrations ALTER COLUMN id SET DEFAULT nextval('drizzle.__drizzle_migrations_id_seq'::regclass);


--
-- Name: __drizzle_migrations __drizzle_migrations_pkey; Type: CONSTRAINT; Schema: drizzle; Owner: neondb_owner
--

ALTER TABLE ONLY drizzle.__drizzle_migrations
    ADD CONSTRAINT __drizzle_migrations_pkey PRIMARY KEY (id);


--
-- Name: account account_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.account
    ADD CONSTRAINT account_pkey PRIMARY KEY (id);


--
-- Name: invoice invoice_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_pkey PRIMARY KEY (id);


--
-- Name: session session_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.session
    ADD CONSTRAINT session_pkey PRIMARY KEY (id);


--
-- Name: session session_token_unique; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.session
    ADD CONSTRAINT session_token_unique UNIQUE (token);


--
-- Name: source_folder source_folder_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.source_folder
    ADD CONSTRAINT source_folder_pkey PRIMARY KEY (id);


--
-- Name: source source_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.source
    ADD CONSTRAINT source_pkey PRIMARY KEY (id);


--
-- Name: user user_email_unique; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_email_unique UNIQUE (email);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: verification verification_pkey; Type: CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.verification
    ADD CONSTRAINT verification_pkey PRIMARY KEY (id);


--
-- Name: account account_user_id_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.account
    ADD CONSTRAINT account_user_id_user_id_fk FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: invoice invoice_source_id_source_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_source_id_source_id_fk FOREIGN KEY (source_id) REFERENCES public.source(id) ON DELETE SET NULL;


--
-- Name: invoice invoice_user_id_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_user_id_user_id_fk FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: session session_user_id_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.session
    ADD CONSTRAINT session_user_id_user_id_fk FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: source_folder source_folder_source_id_source_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.source_folder
    ADD CONSTRAINT source_folder_source_id_source_id_fk FOREIGN KEY (source_id) REFERENCES public.source(id) ON DELETE CASCADE;


--
-- Name: source source_user_id_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: neondb_owner
--

ALTER TABLE ONLY public.source
    ADD CONSTRAINT source_user_id_user_id_fk FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO neon_superuser WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: cloud_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE cloud_admin IN SCHEMA public GRANT ALL ON TABLES TO neon_superuser WITH GRANT OPTION;


--
-- PostgreSQL database dump complete
--

\unrestrict NM0LqJUdlxd1D28EpUDPyF72YJ2NKdrsWcvUS4t7H0qCerSV3nuZYuGHQME0Y6e


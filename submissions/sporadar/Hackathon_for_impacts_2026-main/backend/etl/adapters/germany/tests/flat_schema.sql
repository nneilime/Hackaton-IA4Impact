-- Test fixture reconstructed from the saved France public-schema inspection.
-- Not an application migration. Only load into a disposable germany_test database.
CREATE TABLE "collection_runs" (
  "run_id" bigserial NOT NULL,
  "source_id" text NOT NULL,
  "started_at" timestamp with time zone NOT NULL DEFAULT now(),
  "finished_at" timestamp with time zone,
  "input_file" text,
  "rows_read" integer,
  "rows_written" integer,
  "status" text NOT NULL DEFAULT 'running'::text,
  "notes" text
);
CREATE TABLE "field_evidence" (
  "evidence_id" bigserial NOT NULL,
  "entity_type" text NOT NULL,
  "entity_id" text NOT NULL,
  "field_name" text NOT NULL,
  "value_original" text,
  "excerpt" text,
  "document_url" text,
  "page_number" integer,
  "extraction_method" text NOT NULL,
  "model_name" text,
  "confidence" numeric,
  "validation_status" text NOT NULL DEFAULT 'automatically_extracted'::text,
  "collected_at" timestamp with time zone NOT NULL DEFAULT now()
);
CREATE TABLE "product_aliases" (
  "alias_id" text NOT NULL,
  "product_id" text NOT NULL,
  "alias_name" text NOT NULL,
  "country_code" character(2),
  "relationship_type" text NOT NULL,
  "confidence" numeric,
  "evidence" text,
  "review_status" text NOT NULL,
  "is_synthetic" boolean NOT NULL
);
CREATE TABLE "products" (
  "product_id" text NOT NULL,
  "commercial_name" text NOT NULL,
  "active_entity_original" text,
  "active_entity_normalized" text,
  "formulation_code" text,
  "is_synthetic" boolean NOT NULL,
  "validation_status" text NOT NULL
);
CREATE TABLE "registrations" (
  "registration_id" text NOT NULL,
  "product_id" text NOT NULL,
  "country_code" character(2) NOT NULL,
  "authority_name" text NOT NULL,
  "registration_number" text,
  "status_original" text,
  "status_normalized" text NOT NULL,
  "approval_date" date,
  "expiration_date" date,
  "source_id" text NOT NULL,
  "source_record_url" text NOT NULL,
  "collected_at" timestamp with time zone NOT NULL,
  "validation_status" text NOT NULL,
  "is_synthetic" boolean NOT NULL
);
CREATE TABLE "source_registry" (
  "source_id" text NOT NULL,
  "official_name" text NOT NULL,
  "country_or_region" text NOT NULL,
  "base_url" text,
  "access_method" text NOT NULL,
  "data_format" text,
  "license_name" text,
  "access_and_reuse_limits" text,
  "manual_validation_required" boolean NOT NULL,
  "notes" text
);
CREATE TABLE "uses" (
  "use_id" text NOT NULL,
  "registration_id" text NOT NULL,
  "crop_name_original" text,
  "crop_name_normalized" text,
  "eppo_crop_code" text,
  "target_name_original" text,
  "target_name_normalized" text,
  "eppo_target_code" text,
  "application_method" text,
  "dose_value" numeric,
  "dose_unit_original" text,
  "dose_unit_normalized" text,
  "max_applications" integer,
  "application_interval_days" numeric,
  "phi_days" numeric,
  "rei_hours" numeric,
  "restrictions_original" text,
  "validation_status" text NOT NULL,
  "is_synthetic" boolean NOT NULL
);
ALTER TABLE "collection_runs" ADD CONSTRAINT "collection_runs_pkey" PRIMARY KEY (run_id);
ALTER TABLE "collection_runs" ADD CONSTRAINT "collection_runs_status_check" CHECK ((status = ANY (ARRAY['running'::text, 'success'::text, 'failed'::text, 'source_unavailable'::text])));
ALTER TABLE "field_evidence" ADD CONSTRAINT "field_evidence_confidence_check" CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)));
ALTER TABLE "field_evidence" ADD CONSTRAINT "field_evidence_entity_type_check" CHECK ((entity_type = ANY (ARRAY['product'::text, 'registration'::text, 'use'::text])));
ALTER TABLE "field_evidence" ADD CONSTRAINT "field_evidence_pkey" PRIMARY KEY (evidence_id);
ALTER TABLE "field_evidence" ADD CONSTRAINT "field_evidence_validation_status_check" CHECK ((validation_status = ANY (ARRAY['automatically_extracted'::text, 'to_verify'::text, 'validated'::text, 'rejected'::text, 'obsolete'::text, 'source_unavailable'::text])));
ALTER TABLE "product_aliases" ADD CONSTRAINT "product_aliases_confidence_check" CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)));
ALTER TABLE "product_aliases" ADD CONSTRAINT "product_aliases_country_code_check" CHECK ((country_code ~ '^[A-Z]{2}$'::text));
ALTER TABLE "product_aliases" ADD CONSTRAINT "product_aliases_pkey" PRIMARY KEY (alias_id);
ALTER TABLE "product_aliases" ADD CONSTRAINT "product_aliases_relationship_type_check" CHECK ((relationship_type = ANY (ARRAY['alternate_name'::text, 'historical_name'::text, 'sister_product_candidate'::text, 'confirmed_sister_product'::text])));
ALTER TABLE "products" ADD CONSTRAINT "products_pkey" PRIMARY KEY (product_id);
ALTER TABLE "products" ADD CONSTRAINT "products_validation_status_check" CHECK ((validation_status = ANY (ARRAY['automatically_extracted'::text, 'to_verify'::text, 'validated'::text, 'rejected'::text, 'obsolete'::text, 'source_unavailable'::text])));
ALTER TABLE "registrations" ADD CONSTRAINT "registrations_country_code_check" CHECK ((country_code ~ '^[A-Z]{2}$'::text));
ALTER TABLE "registrations" ADD CONSTRAINT "registrations_pkey" PRIMARY KEY (registration_id);
ALTER TABLE "registrations" ADD CONSTRAINT "registrations_source_record_url_check" CHECK ((source_record_url ~ '^https?://'::text));
ALTER TABLE "registrations" ADD CONSTRAINT "registrations_status_normalized_check" CHECK ((status_normalized = ANY (ARRAY['active'::text, 'expired'::text, 'withdrawn'::text, 'pending'::text, 'unknown'::text])));
ALTER TABLE "registrations" ADD CONSTRAINT "registrations_validation_status_check" CHECK ((validation_status = ANY (ARRAY['automatically_extracted'::text, 'to_verify'::text, 'validated'::text, 'rejected'::text, 'obsolete'::text, 'source_unavailable'::text])));
ALTER TABLE "source_registry" ADD CONSTRAINT "source_registry_base_url_check" CHECK (((base_url IS NULL) OR (base_url ~ '^https?://'::text)));
ALTER TABLE "source_registry" ADD CONSTRAINT "source_registry_pkey" PRIMARY KEY (source_id);
ALTER TABLE "uses" ADD CONSTRAINT "uses_application_interval_days_check" CHECK ((application_interval_days >= (0)::numeric));
ALTER TABLE "uses" ADD CONSTRAINT "uses_max_applications_check" CHECK ((max_applications >= 0));
ALTER TABLE "uses" ADD CONSTRAINT "uses_phi_days_check" CHECK ((phi_days >= (0)::numeric));
ALTER TABLE "uses" ADD CONSTRAINT "uses_pkey" PRIMARY KEY (use_id);
ALTER TABLE "uses" ADD CONSTRAINT "uses_rei_hours_check" CHECK ((rei_hours >= (0)::numeric));
ALTER TABLE "uses" ADD CONSTRAINT "uses_validation_status_check" CHECK ((validation_status = ANY (ARRAY['automatically_extracted'::text, 'to_verify'::text, 'validated'::text, 'rejected'::text, 'obsolete'::text, 'source_unavailable'::text])));
ALTER TABLE "collection_runs" ADD CONSTRAINT "collection_runs_source_id_fkey" FOREIGN KEY (source_id) REFERENCES source_registry(source_id);
ALTER TABLE "product_aliases" ADD CONSTRAINT "product_aliases_product_id_fkey" FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE;
ALTER TABLE "registrations" ADD CONSTRAINT "registrations_product_id_fkey" FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE;
ALTER TABLE "registrations" ADD CONSTRAINT "registrations_source_id_fkey" FOREIGN KEY (source_id) REFERENCES source_registry(source_id);
ALTER TABLE "uses" ADD CONSTRAINT "uses_registration_id_fkey" FOREIGN KEY (registration_id) REFERENCES registrations(registration_id) ON DELETE CASCADE;

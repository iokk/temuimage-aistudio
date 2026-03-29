ALTER TABLE "User"
    ADD COLUMN "issuer" TEXT NOT NULL DEFAULT 'internal',
    ADD COLUMN "subject" TEXT NOT NULL DEFAULT '',
    ADD COLUMN "emailVerified" BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN "lastLoginAt" TIMESTAMP(3);

UPDATE "User"
SET "subject" = "id"
WHERE "subject" = '';

UPDATE "User"
SET "subject" = 'system',
    "emailVerified" = true
WHERE "id" = 'system';

CREATE UNIQUE INDEX "User_issuer_subject_key" ON "User"("issuer", "subject");

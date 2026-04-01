ALTER TABLE "Membership"
    ADD COLUMN "activeProjectId" TEXT;

ALTER TABLE "Membership"
    ADD CONSTRAINT "Membership_activeProjectId_fkey"
    FOREIGN KEY ("activeProjectId") REFERENCES "Project"("id") ON DELETE SET NULL ON UPDATE CASCADE;

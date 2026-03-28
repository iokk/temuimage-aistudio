import { PrismaClient } from "@prisma/client"

const prisma = new PrismaClient()

async function main() {
  await prisma.user.upsert({
    where: { email: "system@xiaobaitu.local" },
    update: {
      name: "System",
      mode: "personal",
    },
    create: {
      id: "system",
      email: "system@xiaobaitu.local",
      name: "System",
      mode: "personal",
    },
  })
}

main()
  .catch((error) => {
    console.error(error)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })

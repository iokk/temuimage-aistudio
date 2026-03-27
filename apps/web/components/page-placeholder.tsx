export function PagePlaceholder({
  heading,
  description,
}: {
  heading: string
  description: string
}) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
      <h3 className="text-xl font-bold text-slate-950">{heading}</h3>
      <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">{description}</p>
    </div>
  )
}

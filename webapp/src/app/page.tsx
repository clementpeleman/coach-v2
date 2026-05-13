export default function Home() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-8">
      <h1 className="text-3xl font-semibold">Sports Hub</h1>
      <p className="mt-3 max-w-2xl text-slate-600">
        Eerste webversie met Garmin-koppeling, activiteitsoverzicht en basis dashboard.
        Gebruik eerst <a className="underline" href="/login">Login</a> om een user ID te kiezen
        en je Garmin account te verbinden.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <a className="rounded-md bg-slate-900 px-4 py-2 text-white" href="/login">
          Start met Garmin koppeling
        </a>
        <a className="rounded-md border border-slate-300 px-4 py-2" href="/dashboard">
          Bekijk dashboard
        </a>
      </div>
    </div>
  );
}

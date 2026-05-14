import Link from "next/link";
import { Zap, Activity, TrendingUp, MessageCircle } from "lucide-react";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-2xl py-16 text-center">
      <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100">
        <Zap className="h-7 w-7 text-emerald-600" />
      </div>

      <h1 className="text-4xl font-bold tracking-tight">Sports Hub</h1>
      <p className="mx-auto mt-4 max-w-md text-base text-slate-600">
        Koppel je Garmin, analyseer je trainingen en krijg persoonlijke coaching — alles in
        één platform.
      </p>

      <div className="mt-10 flex justify-center gap-3">
        <Link
          href="/login"
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-emerald-700"
        >
          Start met Garmin
        </Link>
        <Link
          href="/dashboard"
          className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium shadow-sm hover:bg-slate-50"
        >
          Ga naar Dashboard
        </Link>
      </div>

      <div className="mx-auto mt-16 grid max-w-lg gap-6 sm:grid-cols-3">
        <FeatureCard
          icon={<Activity className="h-5 w-5 text-emerald-600" />}
          title="Activiteiten"
          description="Al je runs en rides op één plek"
        />
        <FeatureCard
          icon={<TrendingUp className="h-5 w-5 text-emerald-600" />}
          title="Trends"
          description="Volume, hartslag en progressie"
        />
        <FeatureCard
          icon={<MessageCircle className="h-5 w-5 text-emerald-600" />}
          title="AI Coach"
          description="Persoonlijk advies op basis van data"
        />
      </div>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 text-left">
      <div className="mb-3">{icon}</div>
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{description}</p>
    </div>
  );
}

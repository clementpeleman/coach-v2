import { Bike, Footprints } from "lucide-react";

type Props = {
  type: string;
};

export default function SportBadge({ type }: Props) {
  const normalized = type.toUpperCase();

  if (normalized.includes("RUN")) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
        <Footprints className="h-3 w-3" />
        Run
      </span>
    );
  }

  if (normalized.includes("CYCL")) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
        <Bike className="h-3 w-3" />
        Ride
      </span>
    );
  }

  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
      {type}
    </span>
  );
}

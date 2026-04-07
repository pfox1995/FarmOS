import { useState, useEffect } from "react";
import { MdWarning, MdClose } from "react-icons/md";
import type { MissingFieldAlert } from "@/types";

interface Props {
  fetchMissingFields: (
    dateFrom: string,
    dateTo: string,
  ) => Promise<{ missing_fields: MissingFieldAlert[]; total: number } | null>;
  onEditEntry?: (entryId: number) => void;
}

export default function MissingFieldsAlert({
  fetchMissingFields,
  onEditEntry,
}: Props) {
  const [alerts, setAlerts] = useState<MissingFieldAlert[]>([]);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    const weekAgo = new Date(Date.now() - 7 * 86400000)
      .toISOString()
      .slice(0, 10);
    fetchMissingFields(weekAgo, today).then((res) => {
      if (res && res.total > 0) setAlerts(res.missing_fields);
    });
  }, [fetchMissingFields]);

  if (dismissed || alerts.length === 0) return null;

  return (
    <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-2">
          <MdWarning className="text-amber-500 text-xl mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800">
              누락 항목 {alerts.length}건
            </p>
            <ul className="mt-2 space-y-1">
              {alerts.slice(0, 5).map((alert, i) => {
                const dateLabel = alert.work_date
                  ? new Date(alert.work_date).toLocaleDateString("ko-KR", {
                      month: "long",
                      day: "numeric",
                    })
                  : "";
                const timeLabel = alert.created_at
                  ? new Date(alert.created_at).toLocaleTimeString("ko-KR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "";
                const tag = [dateLabel, alert.crop, timeLabel]
                  .filter(Boolean)
                  .join(" · ");
                return (
                  <li key={i} className="text-xs text-amber-700">
                    <button
                      onClick={() => onEditEntry?.(alert.entry_id)}
                      className="text-left cursor-pointer hover:text-amber-900 hover:underline"
                    >
                      {tag && (
                        <span className="font-medium text-amber-800">
                          [{tag}]{" "}
                        </span>
                      )}
                      {alert.message}
                    </button>
                  </li>
                );
              })}
              {alerts.length > 5 && (
                <li className="text-xs text-amber-500">
                  외 {alerts.length - 5}건
                </li>
              )}
            </ul>
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-amber-400 hover:text-amber-600 cursor-pointer"
        >
          <MdClose />
        </button>
      </div>
    </div>
  );
}

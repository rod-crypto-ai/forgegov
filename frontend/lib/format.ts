const usd = {
  full: new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }),
  compact: new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 2 }),
};

export function formatUsd(value: string | number, style: keyof typeof usd = "full") {
  const amount = Number(value);
  return Number.isFinite(amount) ? usd[style].format(amount) : "—";
}

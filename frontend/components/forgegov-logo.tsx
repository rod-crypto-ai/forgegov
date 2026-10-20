import Image from "next/image";

export function ForgeGovMark({ className = "" }: { className?: string }) {
  return (
    <span className={`forge-logo ${className}`.trim()} aria-hidden="true">
      <Image
        src="/brand/forgegov-mark.png"
        alt=""
        width={64}
        height={64}
        priority
      />
    </span>
  );
}

export function ForgeGovAuthBrand({ subtitle }: { subtitle: string }) {
  return (
    <div className="auth-brand">
      <ForgeGovMark />
      <div>
        <b className="forgegov-wordmark"><span>FORGE</span><em>GOV</em></b>
        <small>{subtitle}</small>
      </div>
    </div>
  );
}

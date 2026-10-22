export function AgentOpsLogo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand" aria-label="AgentOps Web">
      <span className="brand-mark" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      {!compact && (
        <span className="brand-type">
          AgentOps <em>Web</em>
        </span>
      )}
    </div>
  );
}

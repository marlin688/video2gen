import React from "react";
import { useCurrentFrame } from "remotion";

interface IconProps {
  size?: number;
  color?: string;
  glowColor?: string;
}

const IconWrapper: React.FC<
  IconProps & { children: React.ReactNode }
> = ({ size = 48, glowColor, children }) => {
  const frame = useCurrentFrame();
  const glowOpacity = glowColor
    ? 0.4 + 0.2 * Math.sin(frame * 0.08)
    : 0;

  return (
    <div
      style={{
        width: size,
        height: size,
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {glowColor && (
        <div
          style={{
            position: "absolute",
            inset: -size * 0.3,
            borderRadius: "50%",
            background: `radial-gradient(circle, ${glowColor}${Math.round(glowOpacity * 255).toString(16).padStart(2, "0")} 0%, transparent 70%)`,
          }}
        />
      )}
      {children}
    </div>
  );
};

export const BrainIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a4 4 0 0 1 4 4c0 .6-.1 1.1-.4 1.6A4 4 0 0 1 18 11c0 .8-.2 1.5-.7 2.1A4 4 0 0 1 14 18h-1v4" />
        <path d="M12 2a4 4 0 0 0-4 4c0 .6.1 1.1.4 1.6A4 4 0 0 0 6 11c0 .8.2 1.5.7 2.1A4 4 0 0 0 10 18h1" />
        <path d="M8 11h8" />
        <path d="M9 7h6" />
        <path d="M9 15h6" />
      </svg>
    </IconWrapper>
  );
};

export const DatabaseIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5" />
        <path d="M3 12c0 1.7 4 3 9 3s9-1.3 9-3" />
      </svg>
    </IconWrapper>
  );
};

export const SearchIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" />
        <path d="M21 21l-4.35-4.35" />
        <path d="M11 8a3 3 0 0 0-3 3" opacity={0.5} />
      </svg>
    </IconWrapper>
  );
};

export const CubeIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2l9 5v10l-9 5-9-5V7l9-5z" />
        <path d="M12 12l9-5" />
        <path d="M12 12l-9-5" />
        <path d="M12 12v10" />
      </svg>
    </IconWrapper>
  );
};

export const RobotIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="8" width="18" height="12" rx="2" />
        <path d="M12 2v6" />
        <circle cx="12" cy="2" r="1" fill={color} />
        <circle cx="9" cy="14" r="1.5" fill={color} />
        <circle cx="15" cy="14" r="1.5" fill={color} />
        <path d="M9 18h6" />
        <path d="M1 12h2" />
        <path d="M21 12h2" />
      </svg>
    </IconWrapper>
  );
};

export const CodeIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
        <line x1="14" y1="4" x2="10" y2="20" opacity={0.6} />
      </svg>
    </IconWrapper>
  );
};

// --- New icons ---

export const CloudIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
      </svg>
    </IconWrapper>
  );
};

export const ApiIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 6h16M4 12h16M4 18h16" />
        <circle cx="8" cy="6" r="1.5" fill={color} />
        <circle cx="16" cy="12" r="1.5" fill={color} />
        <circle cx="12" cy="18" r="1.5" fill={color} />
      </svg>
    </IconWrapper>
  );
};

export const LockIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        <circle cx="12" cy="16" r="1" fill={color} />
      </svg>
    </IconWrapper>
  );
};

export const LightningIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    </IconWrapper>
  );
};

export const ServerIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
        <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
        <line x1="6" y1="6" x2="6.01" y2="6" />
        <line x1="6" y1="18" x2="6.01" y2="18" />
      </svg>
    </IconWrapper>
  );
};

export const TerminalIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <polyline points="4 17 10 11 4 5" />
        <line x1="12" y1="19" x2="20" y2="19" />
      </svg>
    </IconWrapper>
  );
};

export const GitIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="18" r="3" />
        <circle cx="6" cy="6" r="3" />
        <circle cx="18" cy="6" r="3" />
        <path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9" />
        <path d="M12 12v3" />
      </svg>
    </IconWrapper>
  );
};

export const DockerIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 15h18c0 3-2 6-7 6-4 0-7-2-8-4" />
        <rect x="5" y="11" width="3" height="3" rx="0.5" />
        <rect x="9" y="11" width="3" height="3" rx="0.5" />
        <rect x="13" y="11" width="3" height="3" rx="0.5" />
        <rect x="9" y="7" width="3" height="3" rx="0.5" />
        <rect x="13" y="7" width="3" height="3" rx="0.5" />
        <rect x="5" y="7" width="3" height="3" rx="0.5" />
      </svg>
    </IconWrapper>
  );
};

export const KubernetesIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
        <circle cx="12" cy="12" r="3" />
        <path d="M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" />
      </svg>
    </IconWrapper>
  );
};

export const AwsIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
        <path d="M8 16l2-4 2 4" />
        <path d="M14 16l1.5-4 1.5 4" />
      </svg>
    </IconWrapper>
  );
};

export const GlobeIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    </IconWrapper>
  );
};

export const ChartIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
        <line x1="2" y1="20" x2="22" y2="20" />
      </svg>
    </IconWrapper>
  );
};

export const ShieldIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <polyline points="9 12 11 14 15 10" />
      </svg>
    </IconWrapper>
  );
};

export const RocketIcon: React.FC<IconProps> = (props) => {
  const { size = 48, color = "#ffffff" } = props;
  return (
    <IconWrapper {...props}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
        <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
        <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
        <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
      </svg>
    </IconWrapper>
  );
};

export const ICON_MAP: Record<string, React.FC<IconProps>> = {
  brain: BrainIcon,
  database: DatabaseIcon,
  search: SearchIcon,
  cube: CubeIcon,
  robot: RobotIcon,
  code: CodeIcon,
  cloud: CloudIcon,
  api: ApiIcon,
  lock: LockIcon,
  lightning: LightningIcon,
  server: ServerIcon,
  terminal: TerminalIcon,
  git: GitIcon,
  docker: DockerIcon,
  kubernetes: KubernetesIcon,
  aws: AwsIcon,
  globe: GlobeIcon,
  chart: ChartIcon,
  shield: ShieldIcon,
  rocket: RocketIcon,
};

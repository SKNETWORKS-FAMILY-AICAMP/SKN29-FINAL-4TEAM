type WaterDropBubblesProps = {
  className?: string;
};

export default function WaterDropBubbles({
  className = "",
}: WaterDropBubblesProps) {
  return (
    <span
      className={`waterdrop-bubbles ${className}`.trim()}
      aria-hidden="true"
    >
      <i className="waterdrop-bubbles__item waterdrop-bubbles__item--large" />
      <i className="waterdrop-bubbles__item waterdrop-bubbles__item--medium" />
      <i className="waterdrop-bubbles__item waterdrop-bubbles__item--small" />
    </span>
  );
}

import { Link } from "react-router-dom";

export default function ConsultantHeaderBrand() {
  return (
    <Link
      className="simple-brand consultant-header-brand"
      to="/"
      aria-label="Water Bridge 홈으로 이동"
    >
      <span className="simple-brand__wordmark" aria-hidden="true">
        <span className="simple-brand__wordmark-water">Water</span>
        <span className="simple-brand__wordmark-bridge">Bridge</span>
      </span>
    </Link>
  );
}

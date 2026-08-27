import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { Link } from "react-router-dom";

import { ROUTE_PATHS } from "../../app/router/routePaths";
import "./LandingPage.css";

interface JourneySegment {
  angle: number;
  delay: number;
  left: number;
  top: number;
  width: number;
}

const JOURNEY_STEPS = [
  {
    title: "고객 앱",
    description: (
      <>
        증상과 문의를
        <br />
        입력합니다.
      </>
    ),
  },
  {
    title: "AI 정리",
    description: (
      <>
        문의와 안내 결과를
        <br />
        핵심 정보로 정리합니다.
      </>
    ),
  },
  {
    title: "상담사 웹",
    description: (
      <>
        정리된 내용을 확인하고
        <br />
        신속하게 대응합니다.
      </>
    ),
  },
  {
    title: "방문 연결",
    description: (
      <>
        필요 시 방문 서비스를
        <br />
        연결합니다.
      </>
    ),
  },
] as const;

function prefersReducedMotion() {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export default function LandingPage() {
  const heroRef = useRef<HTMLElement | null>(null);
  const continuationRef = useRef<HTMLElement | null>(null);
  const nodeRefs = useRef<Array<HTMLElement | null>>([]);
  const [segments, setSegments] = useState<JourneySegment[]>([]);
  const [animateLine, setAnimateLine] = useState(
    () => !prefersReducedMotion(),
  );
  const [motionReady, setMotionReady] = useState(false);
  const [continuationVisible, setContinuationVisible] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);

  useEffect(() => {
    const previousTitle = document.title;
    document.title =
      "Water Bridge | 고객 앱과 상담사 웹을 잇는 통합 서비스";

    return () => {
      document.title = previousTitle;
    };
  }, []);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setReducedMotion(mediaQuery.matches);
    updatePreference();
    mediaQuery.addEventListener?.("change", updatePreference);

    return () => mediaQuery.removeEventListener?.("change", updatePreference);
  }, []);

  useEffect(() => {
    if (reducedMotion) return;

    const frameId = window.requestAnimationFrame(() => setMotionReady(true));
    return () => window.cancelAnimationFrame(frameId);
  }, [reducedMotion]);

  useEffect(() => {
    if (!animateLine) return;

    const timeoutId = window.setTimeout(() => setAnimateLine(false), 1900);
    return () => window.clearTimeout(timeoutId);
  }, [animateLine]);

  useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return;

    let frameId = 0;
    let active = true;

    const drawJourneyLine = () => {
      if (!active || !heroRef.current) return;

      const heroRect = heroRef.current.getBoundingClientRect();
      const points = nodeRefs.current
        .map((node) => {
          if (!node) return null;
          const rect = node.getBoundingClientRect();
          return {
            x: rect.left - heroRect.left + rect.width / 2,
            y: rect.top - heroRect.top + rect.height / 2,
          };
        })
        .filter((point): point is { x: number; y: number } => point !== null);

      if (points.length !== JOURNEY_STEPS.length) return;

      setSegments(
        points.slice(0, -1).map((start, index) => {
          const end = points[index + 1];
          const deltaX = end.x - start.x;
          const deltaY = end.y - start.y;
          return {
            left: start.x,
            top: start.y,
            width: Math.hypot(deltaX, deltaY),
            angle: (Math.atan2(deltaY, deltaX) * 180) / Math.PI,
            delay: 680 + index * 180,
          };
        }),
      );
    };

    const scheduleDraw = () => {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(drawJourneyLine);
    };

    scheduleDraw();

    const resizeObserver =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(scheduleDraw);
    resizeObserver?.observe(hero);
    nodeRefs.current.forEach((node) => {
      if (node) resizeObserver?.observe(node);
    });
    window.addEventListener("resize", scheduleDraw);

    if (document.fonts) {
      void document.fonts.ready.then(scheduleDraw);
    }

    return () => {
      active = false;
      window.cancelAnimationFrame(frameId);
      resizeObserver?.disconnect();
      window.removeEventListener("resize", scheduleDraw);
    };
  }, []);

  useEffect(() => {
    const continuation = continuationRef.current;
    if (!continuation || reducedMotion || typeof IntersectionObserver === "undefined") {
      setContinuationVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setContinuationVisible(true);
        observer.disconnect();
      },
      { threshold: 0.24 },
    );
    observer.observe(continuation);

    return () => observer.disconnect();
  }, [reducedMotion]);

  const pageClassName = [
    "landing-page",
    !reducedMotion && !motionReady ? "landing-page--motion-pending" : "",
    motionReady ? "landing-page--motion-ready" : "",
    reducedMotion ? "landing-page--reduced-motion" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={pageClassName}>
      <a className="landing-skip-link" href="#landing-main-content">
        본문으로 바로가기
      </a>

      <header className="landing-site-header">
        <a
          className="landing-brand"
          href="#landing-main-content"
          aria-label="Water Bridge 홈"
        >
          <img
            src="/images/landing/water-bridge-logo.png"
            alt="Water Bridge"
          />
        </a>
        <nav aria-label="주요 메뉴">
          <Link to={ROUTE_PATHS.login}>로그인</Link>
        </nav>
      </header>

      <main id="landing-main-content">
        <section
          ref={heroRef}
          className="landing-hero"
          id="service"
          aria-labelledby="landing-hero-title"
        >
          <div className="landing-journey-line" aria-hidden="true">
            {segments.map((segment, index) => {
              const style = {
                left: segment.left,
                top: segment.top,
                width: segment.width,
                "--landing-segment-angle": `${segment.angle}deg`,
                "--landing-segment-delay": `${segment.delay}ms`,
              } as CSSProperties;
              return (
                <span
                  key={index}
                  className={
                    animateLine && !reducedMotion
                      ? "landing-journey-line__segment landing-journey-line__segment--animated"
                      : "landing-journey-line__segment"
                  }
                  data-journey-segment={index + 1}
                  style={style}
                />
              );
            })}
          </div>

          <div className="landing-hero-copy">
            <p className="landing-eyebrow">
              고객 앱과 상담사 웹을 잇는 통합 서비스
            </p>
            <h1 id="landing-hero-title">
              <span className="landing-hero-title__line">
                앱의 <em>문의</em>가,
              </span>
              <span className="landing-hero-title__line">
                상담사의 <em>다음 행동</em>이
              </span>
              <span className="landing-hero-title__line">됩니다.</span>
            </h1>
            <p className="landing-hero-description">
              고객이 입력한 증상과 AI 안내 결과를
              <br />
              상담사에게 전달하고, 필요한 경우
              <br />
              방문 서비스까지 연결합니다.
            </p>
            <Link className="landing-primary-button" to={ROUTE_PATHS.login}>
              로그인 하기
              <span aria-hidden="true">→</span>
            </Link>
          </div>

          <ol
            className="landing-journey-steps"
            aria-label="Water Bridge 서비스 이용 흐름"
          >
            {JOURNEY_STEPS.map((step, index) => (
              <li
                key={step.title}
                className={`landing-journey-step landing-journey-step--${index + 1}`}
              >
                <div className="landing-journey-step__label">
                  <strong>
                    <b>{String(index + 1).padStart(2, "0")}</b>
                    <span>{step.title}</span>
                  </strong>
                  <p>{step.description}</p>
                </div>
                <i
                  ref={(node) => {
                    nodeRefs.current[index] = node;
                  }}
                  className="landing-journey-step__node"
                  data-journey-node={index + 1}
                  aria-hidden="true"
                />
              </li>
            ))}
          </ol>

          <div
            className="landing-device-cluster"
            role="img"
            aria-label="연결된 고객 앱과 상담사 웹 화면 예시"
          >
            <article className="landing-phone-device" aria-hidden="true">
              <span
                className="landing-phone-device__speaker"
                aria-hidden="true"
              />
              <img
                src="/images/landing/mobile-app-screen-v3.png"
                alt=""
              />
            </article>

            <article className="landing-dashboard-device" aria-hidden="true">
              <div className="landing-device-chrome">
                <span className="landing-chrome-dots">
                  <i />
                  <i />
                  <i />
                </span>
                <strong>Water Bridge</strong>
              </div>
              <div className="landing-dashboard-layout">
                <aside className="landing-dashboard-nav">
                  <span className="landing-nav-logo">W</span>
                  <span className="landing-nav-item landing-nav-item--active">▣</span>
                  <span className="landing-nav-item">▢</span>
                  <span className="landing-nav-item">♙</span>
                  <span className="landing-nav-item">▤</span>
                  <span className="landing-nav-item">⌁</span>
                </aside>
                <div className="landing-dashboard-main">
                  <h2>대시보드</h2>
                  <section className="landing-dashboard-summary">
                    <p>오늘 한눈에 보기</p>
                    <div className="landing-summary-cards">
                      <span><small>신규 문의</small><strong>128</strong><em>건</em></span>
                      <span><small>AI 처리 완료</small><strong>96</strong><em>건</em></span>
                      <span><small>상담 진행</small><strong>54</strong><em>건</em></span>
                      <span><small>방문 예정</small><strong>32</strong><em>건</em></span>
                      <span><small>오늘 완료</small><strong>27</strong><em>건</em></span>
                    </div>
                  </section>
                  <div className="landing-dashboard-grid">
                    <section className="landing-flow-widget">
                      <h3>문의 흐름</h3>
                      <div className="landing-mini-flow">
                        <span>✉<small>문의</small><b>128건</b></span><i />
                        <span>⌘<small>AI</small><b>96건</b></span><i />
                        <span>♙<small>상담</small><b>54건</b></span><i />
                        <span className="active">⌖<small>방문</small><b>32건</b></span><i />
                        <span>✓<small>확인</small><b>27건</b></span>
                      </div>
                    </section>
                    <section className="landing-schedule-widget">
                      <h3>방문 일정</h3>
                      <p><span>오전</span><i><b style={{ width: "48%" }} /></i><em>12건</em></p>
                      <p><span>오후</span><i><b style={{ width: "65%" }} /></i><em>14건</em></p>
                      <p><span>내일</span><i><b style={{ width: "78%" }} /></i><em>18건</em></p>
                    </section>
                    <section className="landing-table-widget">
                      <h3>최근 문의 현황</h3>
                      <div className="landing-fake-table">
                        <span /><span /><span /><span /><span /><span />
                      </div>
                    </section>
                    <section className="landing-chart-widget">
                      <h3>상담 진행 현황</h3>
                      <div className="landing-donut" />
                      <ul>
                        <li>상담 대기</li>
                        <li>상담 중</li>
                        <li>상담 완료</li>
                      </ul>
                    </section>
                  </div>
                </div>
              </div>
            </article>

            <article className="landing-side-device" aria-hidden="true">
              <div className="landing-device-chrome">
                <span className="landing-chrome-dots">
                  <i />
                  <i />
                  <i />
                </span>
                <strong>방문 관리</strong>
              </div>
              <div className="landing-side-device__body">
                <h3>방문 지도</h3>
                <div className="landing-map-area">
                  <i className="landing-pin landing-pin--1">●</i>
                  <i className="landing-pin landing-pin--2">●</i>
                  <i className="landing-pin landing-pin--3">●</i>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section
          ref={continuationRef}
          className={`landing-continuation${continuationVisible ? " landing-continuation--visible" : ""}`}
          id="flow"
          aria-labelledby="landing-continuation-title"
        >
          <span aria-hidden="true" />
          <h2 id="landing-continuation-title">
            정보는 이어지고,
            <br />
            고객은 기다리지 않습니다.
          </h2>
          <p id="safety">
            고객이 남긴 정보는 필요한 담당자에게 안전하게 이어집니다.
          </p>
        </section>
      </main>
    </div>
  );
}

import {
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";

import "./ConsultationStepNavigator.css";

export interface ConsultationStepDefinition {
  id: string;
  title: string;
  description: string;
  content: ReactNode;
}

interface ConsultationStepNavigatorProps {
  steps: readonly ConsultationStepDefinition[];
}

export default function ConsultationStepNavigator({
  steps,
}: ConsultationStepNavigatorProps) {
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const shouldFocusStepHeading = useRef(false);
  const stepHeadingRefs = useRef<Array<HTMLHeadingElement | null>>([]);
  const activeStep = steps[activeStepIndex];

  useEffect(() => {
    if (!shouldFocusStepHeading.current) return;
    stepHeadingRefs.current[activeStepIndex]?.focus();
    shouldFocusStepHeading.current = false;
  }, [activeStepIndex]);

  if (!activeStep) return null;

  const moveToStep = (nextStepIndex: number) => {
    if (nextStepIndex < 0 || nextStepIndex >= steps.length) return;
    shouldFocusStepHeading.current = true;
    setActiveStepIndex(nextStepIndex);
  };

  return (
    <section
      className="consultation-stepper"
      aria-label="상담 처리 단계"
      data-active-step={activeStep.id}
    >
      <header className="consultation-stepper__progress">
        <div>
          <small>GUIDED CONSULTATION</small>
          <strong>
            {activeStepIndex + 1} / {steps.length} 단계
          </strong>
        </div>
        <progress
          aria-label="상담 처리 진행률"
          max={steps.length}
          value={activeStepIndex + 1}
        />
      </header>

      <nav className="consultation-stepper__nav" aria-label="상담 단계 선택">
        <ol>
          {steps.map((step, index) => {
            const isActive = index === activeStepIndex;

            return (
              <li key={step.id}>
                <button
                  type="button"
                  className={isActive ? "is-active" : ""}
                  aria-current={isActive ? "step" : undefined}
                  aria-controls={`consultation-step-panel-${step.id}`}
                  aria-label={`상담 ${index + 1}단계: ${step.title}`}
                  onClick={() => moveToStep(index)}
                >
                  <span className="consultation-stepper__number" aria-hidden="true">
                    {index + 1}
                  </span>
                  <span className="consultation-stepper__nav-copy">
                    <strong>{step.title}</strong>
                    <small>{step.description}</small>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <div className="consultation-stepper__panels">
        {steps.map((step, index) => {
          const isActive = index === activeStepIndex;
          return (
            <section
              key={step.id}
              id={`consultation-step-panel-${step.id}`}
              className="consultation-stepper__panel"
              aria-labelledby={`consultation-step-title-${step.id}`}
              hidden={!isActive}
            >
              <header className="consultation-stepper__panel-head">
                <small>STEP {String(index + 1).padStart(2, "0")}</small>
                <h3
                  id={`consultation-step-title-${step.id}`}
                  ref={(element) => {
                    stepHeadingRefs.current[index] = element;
                  }}
                  tabIndex={-1}
                >
                  {step.title}
                </h3>
                <p>{step.description}</p>
              </header>

              <div className="consultation-stepper__panel-body">
                {step.content}
              </div>

              <footer className="consultation-stepper__footer">
                <button
                  type="button"
                  className="v6-button v6-button--secondary"
                  disabled={index === 0}
                  onClick={() => moveToStep(index - 1)}
                >
                  이전 단계
                </button>
                {index < steps.length - 1 && (
                  <button
                    type="button"
                    className="v6-button v6-button--primary"
                    onClick={() => moveToStep(index + 1)}
                  >
                    다음: {steps[index + 1]?.title}
                  </button>
                )}
              </footer>
            </section>
          );
        })}
      </div>
    </section>
  );
}

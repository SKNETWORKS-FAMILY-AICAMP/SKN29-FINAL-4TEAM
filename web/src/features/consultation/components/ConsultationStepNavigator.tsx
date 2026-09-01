import { type ReactNode, useRef, useState } from "react";

import "./ConsultationStepNavigator.css";

export interface ConsultationStepDefinition {
  id: string;
  title: string;
  description: string;
  content: ReactNode;
}

interface ConsultationStepNavigatorProps {
  initialStepId?: string;
  steps: readonly ConsultationStepDefinition[];
}

export default function ConsultationStepNavigator({
  initialStepId,
  steps,
}: ConsultationStepNavigatorProps) {
  const [activeStepIndex, setActiveStepIndex] = useState(() => {
    const initialIndex = initialStepId
      ? steps.findIndex((step) => step.id === initialStepId)
      : 0;
    return initialIndex >= 0 ? initialIndex : 0;
  });
  const panelsRef = useRef<HTMLDivElement>(null);
  const activeStep = steps[activeStepIndex];

  if (!activeStep) return null;

  const moveToStep = (nextStepIndex: number) => {
    if (nextStepIndex < 0 || nextStepIndex >= steps.length) return;
    setActiveStepIndex(nextStepIndex);
    if (panelsRef.current) panelsRef.current.scrollTop = 0;
  };

  return (
    <section
      className="consultation-stepper"
      aria-label="상담 처리 단계"
      data-active-step={activeStep.id}
    >
      <header className="consultation-stepper__progress">
        <div>
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
                  id={`consultation-step-tab-${step.id}`}
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
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <div ref={panelsRef} className="consultation-stepper__panels">
        {steps.map((step, index) => {
          const isActive = index === activeStepIndex;
          return (
            <section
              key={step.id}
              id={`consultation-step-panel-${step.id}`}
              className="consultation-stepper__panel"
              aria-labelledby={`consultation-step-tab-${step.id}`}
              hidden={!isActive}
            >
              <div className="consultation-stepper__panel-body">
                {step.content}
              </div>
            </section>
          );
        })}
      </div>
    </section>
  );
}

import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type AriaAttributes,
  type KeyboardEvent,
} from "react";
import { createPortal } from "react-dom";

import "./FormSelect.css";

export interface FormSelectOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

interface FormSelectProps extends AriaAttributes {
  id?: string;
  name?: string;
  value: string;
  options: readonly FormSelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  "data-testid"?: string;
}

/** A select-only combobox: focus stays on its trigger while the list is open. */
export default function FormSelect({
  id,
  name,
  value,
  options,
  onChange,
  disabled = false,
  required = false,
  className = "",
  "data-testid": testId,
  ...ariaProps
}: FormSelectProps) {
  const generatedId = useId();
  const triggerId = id ?? `form-select-${generatedId}`;
  const listId = `${triggerId}-options`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const typeaheadRef = useRef({ text: "", lastAt: 0 });
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const selectedIndex = options.findIndex((option) => option.value === value);
  const selectedOption = options[selectedIndex];
  const isExpanded = isOpen && !disabled;
  const enabledIndices = options.flatMap((option, index) => option.disabled ? [] : [index]);

  const openList = (fromEnd = false) => {
    if (disabled || triggerRef.current?.matches(":disabled")) return;
    const initialIndex = selectedIndex >= 0 && !selectedOption?.disabled
      ? selectedIndex
      : (fromEnd ? enabledIndices.at(-1) : enabledIndices[0]) ?? -1;
    setActiveIndex(initialIndex);
    setIsOpen(true);
  };

  const chooseOption = (index: number) => {
    const option = options[index];
    if (disabled || !option || option.disabled) return;
    onChange(option.value);
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  useLayoutEffect(() => {
    if (!isExpanded) return;

    const positionList = () => {
      const trigger = triggerRef.current;
      const list = listRef.current;
      if (!trigger || !list) return;
      const rect = trigger.getBoundingClientRect();
      const gutter = 8;
      const gap = 6;
      const width = Math.min(Math.max(rect.width, 160), window.innerWidth - gutter * 2);
      const below = window.innerHeight - rect.bottom - gap - gutter;
      const above = rect.top - gap - gutter;
      const opensBelow = below >= 220 || below >= above;
      const maxHeight = Math.max(48, Math.min(300, opensBelow ? below : above));
      list.style.width = `${width}px`;
      list.style.maxHeight = `${maxHeight}px`;
      list.style.left = `${Math.max(gutter, Math.min(rect.left, window.innerWidth - width - gutter))}px`;
      list.style.top = `${opensBelow
        ? rect.bottom + gap
        : Math.max(gutter, rect.top - Math.min(list.scrollHeight, maxHeight) - gap)}px`;
    };

    positionList();
    window.addEventListener("resize", positionList);
    window.addEventListener("scroll", positionList, true);
    return () => {
      window.removeEventListener("resize", positionList);
      window.removeEventListener("scroll", positionList, true);
    };
  }, [isExpanded, options.length]);

  useEffect(() => {
    if (!isExpanded) return;
    const closeOutside = (event: Event) => {
      const target = event.target;
      if (
        target instanceof Node &&
        !triggerRef.current?.contains(target) &&
        !listRef.current?.contains(target)
      ) setIsOpen(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("focusin", closeOutside);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("focusin", closeOutside);
    };
  }, [isExpanded]);

  useEffect(() => {
    if (!isExpanded || activeIndex < 0) return;
    document.getElementById(`${listId}-${activeIndex}`)?.scrollIntoView?.({ block: "nearest" });
  }, [activeIndex, isExpanded, listId]);

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (event.key === "Tab") {
      setIsOpen(false);
      return;
    }
    if (event.key === "Escape") {
      if (isExpanded) {
        event.preventDefault();
        event.stopPropagation();
        setIsOpen(false);
      }
      return;
    }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      if (!isExpanded) {
        openList(event.key === "ArrowUp" || event.key === "End");
        if (event.key === "Home") setActiveIndex(enabledIndices[0] ?? -1);
        if (event.key === "End") setActiveIndex(enabledIndices.at(-1) ?? -1);
        return;
      }
      const current = enabledIndices.indexOf(activeIndex);
      const next = event.key === "Home" ? enabledIndices[0]
        : event.key === "End" ? enabledIndices.at(-1)
          : event.key === "ArrowDown" ? enabledIndices[Math.min(current + 1, enabledIndices.length - 1)]
            : enabledIndices[Math.max(current - 1, 0)];
      setActiveIndex(next ?? -1);
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (isExpanded) chooseOption(activeIndex);
      else openList();
      return;
    }
    if (event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) {
      const now = Date.now();
      const text = (now - typeaheadRef.current.lastAt < 700 ? typeaheadRef.current.text : "") + event.key;
      typeaheadRef.current = { text, lastAt: now };
      const match = options.findIndex((option) => !option.disabled && option.label.toLocaleLowerCase().startsWith(text.toLocaleLowerCase()));
      if (match >= 0) {
        event.preventDefault();
        setActiveIndex(match);
        setIsOpen(true);
      }
    }
  };

  return (
    <span className={`wb-form-select ${className}`.trim()}>
      {name && <input type="hidden" name={name} value={value} disabled={disabled} />}
      <button
        {...ariaProps}
        id={triggerId}
        ref={triggerRef}
        type="button"
        role="combobox"
        className="wb-form-select__trigger"
        value={value}
        disabled={disabled}
        data-testid={testId}
        aria-haspopup="listbox"
        aria-expanded={isExpanded}
        aria-controls={isExpanded ? listId : undefined}
        aria-activedescendant={isExpanded && activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
        aria-required={required || undefined}
        onClick={() => isExpanded ? setIsOpen(false) : openList()}
        onKeyDown={handleKeyDown}
      >
        <span className="wb-form-select__value">{selectedOption?.label ?? "선택해 주세요"}</span>
        <svg aria-hidden="true" viewBox="0 0 20 20" className="wb-form-select__chevron">
          <path d="m5 7.5 5 5 5-5" />
        </svg>
      </button>
      {isExpanded && createPortal(
        <div
          id={listId}
          ref={listRef}
          role="listbox"
          aria-label={ariaProps["aria-label"]}
          aria-labelledby={ariaProps["aria-label"] ? undefined : triggerId}
          className="wb-form-select__listbox"
          onMouseDown={(event) => event.preventDefault()}
          onMouseLeave={() => setActiveIndex(-1)}
        >
          {options.map((option, index) => (
            <div
              id={`${listId}-${index}`}
              key={option.value}
              role="option"
              aria-label={option.label}
              aria-describedby={option.description ? `${listId}-${index}-description` : undefined}
              aria-selected={option.value === value}
              aria-disabled={option.disabled || undefined}
              className={`wb-form-select__option${activeIndex === index ? " is-active" : ""}`}
              onMouseMove={() => !option.disabled && setActiveIndex(index)}
              onClick={() => chooseOption(index)}
            >
              <span>{option.label}</span>
              {option.description && <small id={`${listId}-${index}-description`}>{option.description}</small>}
            </div>
          ))}
          {options.length === 0 && <div className="wb-form-select__empty">선택 가능한 항목이 없습니다.</div>}
        </div>,
        document.body,
      )}
    </span>
  );
}

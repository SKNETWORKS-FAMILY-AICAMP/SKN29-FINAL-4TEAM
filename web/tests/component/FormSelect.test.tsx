import { useState } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import FormSelect from "../../src/common/components/form/FormSelect";

const OPTIONS = [
  { value: "NEW", label: "새 문의" },
  { value: "DISABLED", label: "선택 불가", disabled: true },
  { value: "IN_PROGRESS", label: "상담 중", description: "진행 중인 상담" },
  { value: "DONE", label: "상담 완료" },
];

function SelectHarness({ onChange = vi.fn() }: { onChange?: (value: string) => void }) {
  const [value, setValue] = useState("NEW");
  return (
    <div style={{ overflow: "hidden" }}>
      <label htmlFor="status-select">상담 상태</label>
      <FormSelect
        id="status-select"
        name="status"
        value={value}
        options={OPTIONS}
        onChange={(next) => { setValue(next); onChange(next); }}
      />
      <button type="button">다음 입력</button>
    </div>
  );
}

describe("FormSelect", () => {
  it("선택값을 표시하고 바깥 패널에 옵션을 열어 선택한 값만 전달한다", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { container } = render(<SelectHarness onChange={onChange} />);
    const trigger = screen.getByRole("combobox", { name: "상담 상태" });

    expect(trigger).toHaveTextContent("새 문의");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    await user.click(trigger);
    const list = screen.getByRole("listbox");
    expect(list.parentElement).toBe(document.body);
    expect(trigger).toHaveAttribute("aria-controls", list.id);
    expect(within(list).getByRole("option", { name: "새 문의" })).toHaveAttribute("aria-selected", "true");
    const inProgress = within(list).getByRole("option", { name: "상담 중" });
    expect(inProgress).toHaveAccessibleDescription("진행 중인 상담");
    await user.click(inProgress);

    expect(onChange).toHaveBeenCalledExactlyOnceWith("IN_PROGRESS");
    expect(trigger).toHaveTextContent("상담 중");
    expect(trigger).toHaveFocus();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(container.querySelector('input[name="status"]')).toHaveValue("IN_PROGRESS");
  });

  it("현재 선택과 관계없이 커서가 올라간 옵션 하나만 강조한다", async () => {
    const user = userEvent.setup();
    render(<SelectHarness />);
    await user.click(screen.getByRole("combobox", { name: "상담 상태" }));
    const selected = screen.getByRole("option", { name: "새 문의" });
    const hovered = screen.getByRole("option", { name: "상담 완료" });

    await user.hover(hovered);
    expect(hovered).toHaveClass("is-active");
    expect(selected).not.toHaveClass("is-active");
    expect(selected).toHaveAttribute("aria-selected", "true");
    await user.unhover(hovered);
    expect(hovered).not.toHaveClass("is-active");
  });

  it("방향키는 비활성 옵션을 건너뛰고 Home/End/Enter/Space로 선택할 수 있다", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SelectHarness onChange={onChange} />);
    const trigger = screen.getByRole("combobox", { name: "상담 상태" });
    trigger.focus();

    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(trigger).toHaveAttribute("aria-activedescendant", screen.getByRole("option", { name: "상담 중" }).id);
    await user.keyboard("{End}{ArrowUp}{Enter}");
    expect(trigger).toHaveTextContent("상담 중");
    expect(onChange).toHaveBeenLastCalledWith("IN_PROGRESS");

    await user.keyboard(" {Home} ");
    expect(trigger).toHaveTextContent("새 문의");
    expect(onChange).toHaveBeenLastCalledWith("NEW");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("Escape, Tab과 외부 클릭은 값을 바꾸지 않고 목록을 닫는다", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SelectHarness onChange={onChange} />);
    const trigger = screen.getByRole("combobox", { name: "상담 상태" });

    await user.click(trigger);
    await user.keyboard("{End}{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    await user.click(trigger);
    await user.tab();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다음 입력" })).toHaveFocus();
    await user.click(trigger);
    await user.click(screen.getByRole("button", { name: "다음 입력" }));
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("비활성 옵션 선택과 비활성 필드 열기를 차단한다", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { rerender } = render(<FormSelect aria-label="상태" value="NEW" options={OPTIONS} onChange={onChange} />);
    await user.click(screen.getByRole("combobox", { name: "상태" }));
    const disabledOption = screen.getByRole("option", { name: "선택 불가" });
    expect(disabledOption).toHaveAttribute("aria-disabled", "true");
    await user.click(disabledOption);
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    rerender(<FormSelect aria-label="상태" value="NEW" options={OPTIONS} onChange={onChange} disabled />);
    const trigger = screen.getByRole("combobox", { name: "상태" });
    expect(trigger).toBeDisabled();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await user.click(trigger);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("연결된 라벨·필수·오류 안내를 보존하고 label 클릭으로 포커스할 수 있다", async () => {
    const user = userEvent.setup();
    render(
      <>
        <label>대표 증상 *
          <FormSelect value="" onChange={vi.fn()} options={[{ value: "", label: "선택해 주세요" }]}
            required aria-invalid="true" aria-describedby="symptom-error" />
        </label>
        <p id="symptom-error">증상을 선택해 주세요.</p>
      </>,
    );
    const trigger = screen.getByRole("combobox", { name: "대표 증상 *" });
    expect(trigger).toHaveAttribute("aria-required", "true");
    expect(trigger).toHaveAttribute("aria-invalid", "true");
    expect(trigger).toHaveAccessibleDescription("증상을 선택해 주세요.");
    await user.click(screen.getByText("대표 증상 *"));
    expect(trigger).toHaveFocus();
  });

  it("빈 옵션·알 수 없는 기존 값에서도 자동으로 다른 값을 선택하지 않는다", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FormSelect aria-label="기사" value="opaque-missing-id" options={[]} onChange={onChange} />);
    await user.click(screen.getByRole("combobox", { name: "기사" }));
    await user.keyboard("{ArrowDown}{Enter}");
    expect(screen.getByText("선택 가능한 항목이 없습니다.")).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("부모 fieldset이 비활성화된 경우에도 열리지 않는다", async () => {
    const user = userEvent.setup();
    render(<fieldset disabled><FormSelect aria-label="상태" value="NEW" options={OPTIONS} onChange={vi.fn()} /></fieldset>);
    const trigger = screen.getByRole("combobox", { name: "상태" });
    expect(trigger).toBeDisabled();
    await user.click(trigger);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("공간이 부족하면 목록을 위쪽에 배치하고 화면 너비 안에 유지한다", async () => {
    const user = userEvent.setup();
    render(<SelectHarness />);
    const trigger = screen.getByRole("combobox", { name: "상담 상태" });
    vi.spyOn(trigger, "getBoundingClientRect").mockReturnValue({
      width: 240, height: 44, top: window.innerHeight - 50, bottom: window.innerHeight - 6,
      left: window.innerWidth - 100, right: window.innerWidth + 140,
      x: window.innerWidth - 100, y: window.innerHeight - 50, toJSON: () => ({}),
    });
    await user.click(trigger);
    const list = screen.getByRole("listbox");
    Object.defineProperty(list, "scrollHeight", { configurable: true, value: 180 });
    fireEvent(window, new Event("resize"));
    expect(Number.parseFloat(list.style.top)).toBeLessThan(window.innerHeight - 50);
    expect(Number.parseFloat(list.style.left) + Number.parseFloat(list.style.width)).toBeLessThanOrEqual(window.innerWidth - 8);
  });
});

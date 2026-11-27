import { describe, expect, it } from "vitest";
import { formatMoneyInput, percentToRate, rateToPercent, stripMoney, won } from "./format";

describe("won", () => {
  it("콤마와 원을 붙이고 숫자는 그대로 둔다", () => {
    expect(won("5000000")).toBe("5,000,000원");
    expect(won("-95000")).toBe("-95,000원");
    expect(won("1234.5")).toBe("1,234.5원");
    expect(won("0")).toBe("0원");
  });
  it("값이 없으면 줄표", () => {
    expect(won(null)).toBe("—");
    expect(won(undefined)).toBe("—");
  });
});

describe("stripMoney", () => {
  it("콤마·공백·원을 지운다", () => {
    expect(stripMoney("1,234,567원")).toBe("1234567");
    expect(stripMoney(" 3 000 000 ")).toBe("3000000");
    expect(stripMoney("")).toBe("");
  });
  it("숫자와 소수점 외의 글자는 막는다", () => {
    expect(stripMoney("12abc34")).toBe("1234");
    expect(stripMoney("1.5.7")).toBe("1.57");
  });
  it("음수는 허용할 때만 맨 앞 '-'를 남긴다", () => {
    expect(stripMoney("-500", false)).toBe("500");
    expect(stripMoney("-500", true)).toBe("-500");
    expect(stripMoney("5-00", true)).toBe("500");
    expect(stripMoney("-", true)).toBe("-");
  });
  it("입력 도중의 소수점은 남긴다", () => {
    expect(stripMoney("12.", false)).toBe("12.");
  });
});

describe("formatMoneyInput", () => {
  it("천 단위 콤마를 넣는다", () => {
    expect(formatMoneyInput("3000000")).toBe("3,000,000");
    expect(formatMoneyInput("-1234567")).toBe("-1,234,567");
    expect(formatMoneyInput("999")).toBe("999");
    expect(formatMoneyInput("")).toBe("");
    expect(formatMoneyInput("-")).toBe("-");
  });
  it("소수점 아래는 그대로 둔다", () => {
    expect(formatMoneyInput("1234.5678")).toBe("1,234.5678");
    expect(formatMoneyInput("1234.")).toBe("1,234.");
  });
  it("stripMoney와 왕복해도 값이 같다", () => {
    for (const raw of ["0", "1234567", "-8900000", "12.50", "100000000000000000000"]) {
      expect(stripMoney(formatMoneyInput(raw), true)).toBe(raw);
    }
  });
});

describe("percentToRate", () => {
  it("소수점을 두 자리 옮긴다", () => {
    expect(percentToRate("65")).toBe("0.65");
    expect(percentToRate("6.5")).toBe("0.065");
    expect(percentToRate("100")).toBe("1");
    expect(percentToRate("0")).toBe("0");
    expect(percentToRate("0.5")).toBe("0.005");
    expect(percentToRate("99.99")).toBe("0.9999");
    expect(percentToRate("5")).toBe("0.05");
    expect(percentToRate("60.0")).toBe("0.6");
    expect(percentToRate("100.0")).toBe("1");
    expect(percentToRate(" 65 ")).toBe("0.65");
  });
  it("0~100 밖, 빈 값, 숫자 아닌 값은 null", () => {
    expect(percentToRate("100.1")).toBeNull();
    expect(percentToRate("101")).toBeNull();
    expect(percentToRate("1000")).toBeNull();
    expect(percentToRate("abc")).toBeNull();
    expect(percentToRate("-5")).toBeNull();
    expect(percentToRate("")).toBeNull();
    expect(percentToRate("6.")).toBeNull();
    expect(percentToRate("1e2")).toBeNull();
  });
});

describe("rateToPercent", () => {
  it("소수점을 두 자리 옮긴다", () => {
    expect(rateToPercent("0.65")).toBe("65");
    expect(rateToPercent("0.065")).toBe("6.5");
    expect(rateToPercent("1")).toBe("100");
    expect(rateToPercent("0")).toBe("0");
    expect(rateToPercent("0.6")).toBe("60");
    expect(rateToPercent("0.9999")).toBe("99.99");
    expect(rateToPercent("0.005")).toBe("0.5");
    expect(rateToPercent("0.0650")).toBe("6.5");
    expect(rateToPercent("1.0")).toBe("100");
  });
  it("0~1 밖이거나 숫자가 아니면 null", () => {
    expect(rateToPercent("1.1")).toBeNull();
    expect(rateToPercent("2")).toBeNull();
    expect(rateToPercent("-0.5")).toBeNull();
    expect(rateToPercent("abc")).toBeNull();
    expect(rateToPercent("")).toBeNull();
  });
  it("percentToRate와 왕복해도 값이 같다", () => {
    for (const p of ["0", "0.5", "6.5", "33.33", "60", "99.99", "100"]) {
      expect(rateToPercent(percentToRate(p) as string)).toBe(p);
    }
  });
});

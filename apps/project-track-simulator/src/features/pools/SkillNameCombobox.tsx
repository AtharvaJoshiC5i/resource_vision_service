import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

/** Cap only for very large catalogs (performance); datalist-equivalent behavior otherwise. */
const SUGGESTION_HARD_CAP = 400;

type MenuRect = { top: number; left: number; width: number };

function rankSkillSuggestions(catalog: string[], query: string): string[] {
  const q = query.trim().toLowerCase();
  const base = catalog.filter((n) => n.trim());
  if (!q) {
    return [...base].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  }
  const starts: string[] = [];
  const contains: string[] = [];
  for (const name of base) {
    const low = name.toLowerCase();
    if (low.startsWith(q)) starts.push(name);
    else if (low.includes(q)) contains.push(name);
  }
  const cmp = (a: string, b: string) => a.localeCompare(b, undefined, { sensitivity: "base" });
  starts.sort(cmp);
  contains.sort(cmp);
  const merged = [...starts, ...contains];
  return merged.length > SUGGESTION_HARD_CAP ? merged.slice(0, SUGGESTION_HARD_CAP) : merged;
}

export function SkillNameCombobox({
  value,
  onChange,
  suggestions,
  disabled,
  placeholder,
  inputClassName,
  onPick,
}: {
  value: string;
  onChange: (next: string) => void;
  suggestions: string[];
  disabled?: boolean;
  placeholder?: string;
  inputClassName?: string;
  /** Called when user picks a catalog row (exact name). */
  onPick?: (name: string) => void;
}) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [menuRect, setMenuRect] = useState<MenuRect | null>(null);

  const filtered = useMemo(() => rankSkillSuggestions(suggestions, value), [suggestions, value]);

  useEffect(() => {
    setActive(0);
  }, [value, filtered.length]);

  const placeMenu = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setMenuRect({
      top: r.bottom + 4,
      left: r.left,
      width: r.width,
    });
  }, []);

  const showMenu = open && !disabled && filtered.length > 0;

  useLayoutEffect(() => {
    if (!showMenu) {
      setMenuRect(null);
      return;
    }
    placeMenu();
    window.addEventListener("resize", placeMenu);
    window.addEventListener("scroll", placeMenu, true);
    return () => {
      window.removeEventListener("resize", placeMenu);
      window.removeEventListener("scroll", placeMenu, true);
    };
  }, [showMenu, placeMenu, filtered.length, value]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (rootRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const pick = (name: string) => {
    onChange(name);
    onPick?.(name);
    setOpen(false);
    inputRef.current?.focus();
  };

  const menu =
    showMenu && menuRect ? (
      <ul
        ref={menuRef}
        id={listId}
        role="listbox"
        className="rv-skill-combobox__menu rv-skill-combobox__menu--portal"
        style={{
          position: "fixed",
          top: menuRect.top,
          left: menuRect.left,
          width: menuRect.width,
        }}
      >
        {filtered.map((name, i) => (
          <li
            key={name}
            id={`${listId}-opt-${i}`}
            role="option"
            aria-selected={i === active}
            className={`rv-skill-combobox__option ${i === active ? "rv-skill-combobox__option--active" : ""}`}
            onMouseEnter={() => setActive(i)}
            onMouseDown={(e) => {
              e.preventDefault();
              pick(name);
            }}
          >
            <span className="rv-skill-combobox__option-label">{highlightMatch(name, value)}</span>
          </li>
        ))}
      </ul>
    ) : null;

  return (
    <div ref={rootRef} className="rv-skill-combobox">
      <input
        ref={inputRef}
        type="text"
        autoComplete="off"
        spellCheck={false}
        role="combobox"
        aria-expanded={showMenu}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showMenu ? `${listId}-opt-${active}` : undefined}
        className={["rv-skill-combobox__input", inputClassName].filter(Boolean).join(" ")}
        placeholder={placeholder}
        value={value}
        disabled={disabled}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (!showMenu) {
            if ((e.key === "ArrowDown" || e.key === "ArrowUp") && filtered.length) {
              setOpen(true);
              e.preventDefault();
            }
            return;
          }
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, filtered.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter" && filtered[active]) {
            e.preventDefault();
            pick(filtered[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {menu ? createPortal(menu, document.body) : null}
    </div>
  );
}

function highlightMatch(name: string, query: string) {
  const q = query.trim();
  if (!q) return name;
  const idx = name.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return name;
  const before = name.slice(0, idx);
  const match = name.slice(idx, idx + q.length);
  const after = name.slice(idx + q.length);
  return (
    <>
      {before}
      <mark className="rv-skill-combobox__mark">{match}</mark>
      {after}
    </>
  );
}
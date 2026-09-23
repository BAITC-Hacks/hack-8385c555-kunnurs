import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from '../i18n';

function popupPosition(element) {
  const rect = element.getBoundingClientRect();
  const height = window.visualViewport?.height || window.innerHeight;
  const width = window.visualViewport?.width || window.innerWidth;
  if (rect.bottom < 0 || rect.top > height) return null;
  const below = height - rect.bottom - 12;
  const above = rect.top - 12;
  const upward = below < 260 && above > below;
  const maxHeight = Math.max(100, Math.min(340, upward ? above : below));
  const popupWidth = Math.min(Math.max(rect.width, 280), width - 24);
  return { left: Math.max(12, Math.min(rect.left, width - popupWidth - 12)), width: popupWidth, maxHeight, ...(upward ? { bottom: window.innerHeight - rect.top + 6 } : { top: rect.bottom + 6 }) };
}

// A button + listbox: option focus is real DOM focus, including for screen readers.
export function ChoicePicker({ id, value, options, onChange, disabled, invalid, placeholder, searchable = false }) {
  const t = useTranslation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [position, setPosition] = useState(null);
  const trigger = useRef(null);
  const popup = useRef(null);
  const search = useRef(null);
  const list = useRef(null);
  const selected = options.find((item) => item.value === value);
  const filtered = options.filter((item) => `${item.code || ''} ${t(item.label)} ${t(item.group || '')}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  const groups = [...new Set(filtered.map((item) => item.group || ''))];

  function close(restoreFocus = false) {
    setOpen(false);
    if (restoreFocus) trigger.current?.focus();
  }
  function show() {
    if (disabled) return;
    setQuery('');
    const next = popupPosition(trigger.current);
    if (!next) return;
    setPosition(next);
    setOpen(true);
  }
  useLayoutEffect(() => {
    if (!open) return;
    const current = list.current?.querySelector('[aria-selected="true"]');
    const target = search.current || current || list.current?.querySelector('[role="option"]');
    target?.focus({ preventScroll: true });
    (current || (!search.current ? target : null))?.scrollIntoView({ block: 'nearest', behavior: 'instant' });
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const outside = (event) => { if (!popup.current?.contains(event.target) && !trigger.current?.contains(event.target)) setOpen(false); };
    const scrolled = (event) => {
      if (popup.current?.contains(event.target)) return;
      const next = popupPosition(trigger.current);
      if (next) setPosition(next);
      else setOpen(false);
    };
    const resized = () => setOpen(false);
    document.addEventListener('pointerdown', outside);
    document.addEventListener('scroll', scrolled, true);
    window.addEventListener('resize', resized);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('scroll', scrolled, true); window.removeEventListener('resize', resized); };
  }, [open]);
  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);

  function keyboard(event) {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true); return; }
    if (event.key === 'Tab') { close(true); return; }
    const items = [...(list.current?.querySelectorAll('[role="option"]') || [])];
    if (!items.length) return;
    const index = items.indexOf(document.activeElement);
    let next;
    if (event.key === 'ArrowDown') next = Math.min(index + 1, items.length - 1);
    if (event.key === 'ArrowUp') next = index < 0 ? items.length - 1 : Math.max(0, index - 1);
    if (event.target !== search.current && event.key === 'Home') next = 0;
    if (event.target !== search.current && event.key === 'End') next = items.length - 1;
    if (event.target === search.current && event.key === 'Enter') { event.preventDefault(); onChange(filtered[0].value); close(true); return; }
    if (next !== undefined) { event.preventDefault(); items[next].focus({ preventScroll: true }); items[next].scrollIntoView({ block: 'nearest' }); }
  }

  return <>
    <button ref={trigger} id={id} type="button" className="choice-trigger" data-picker-value={value || ''} aria-labelledby={`${id}-label ${id}-value`} aria-invalid={invalid || undefined} aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? `${id}-list` : undefined} disabled={disabled} onClick={() => open ? close(true) : show()} onKeyDown={(event) => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); show(); } }}>
      <span id={`${id}-value`} className="choice-current">{selected?.code && <span className="choice-code">{selected.code}</span>}<span>{t(selected?.label || placeholder)}</span></span>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
    </button>
    {open && !disabled && createPortal(<div ref={popup} className="choice-popup" style={position} onKeyDown={keyboard}>
      {searchable && <div className="choice-search"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></svg><input ref={search} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('Найти меру или направление')} aria-label={t('Поиск мероприятий')} aria-controls={`${id}-list`} autoComplete="off" /></div>}
      <div ref={list} className="choice-options" id={`${id}-list`} role="listbox" aria-labelledby={`${id}-label`}>
        {groups.map((group, groupIndex) => <div key={group} role="group" aria-labelledby={group ? `${id}-group-${groupIndex}` : undefined}>
          {group && <div className="choice-group" id={`${id}-group-${groupIndex}`}>{t(group)}</div>}
          {filtered.filter((item) => (item.group || '') === group).map((item) => <button type="button" role="option" tabIndex={-1} aria-selected={item.value === value} key={item.value} data-option-value={item.value} className="choice-option" onClick={() => { onChange(item.value); close(true); }}>
            <span className="choice-option-copy"><span className="choice-option-title">{item.code && <span className="choice-code">{item.code}</span>}{t(item.label)}</span>{item.detail && <span className="choice-option-detail">{t(item.detail)}{item.lag !== undefined && <> · {t(`${item.lag} кв. до начала эффекта`)}</>}</span>}</span>
            {item.cost !== undefined && <span className="choice-price">{item.cost} <span>{t('ед.')}</span></span>}
            <span className="choice-check" aria-hidden="true">{item.value === value ? '✓' : ''}</span>
          </button>)}
        </div>)}
      </div>
      {!filtered.length && <p className="choice-empty" role="status">{t('Ничего не найдено. Попробуйте другое название.')}</p>}
    </div>, document.body)}
  </>;
}

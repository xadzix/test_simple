import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArrowLeft,
  Bot,
  Boxes,
  Building2,
  Check,
  ChevronRight,
  CircleAlert,
  FileSpreadsheet,
  FolderKanban,
  LoaderCircle,
  Menu,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { api, query, rows } from "./api";

const money = (value) =>
  new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(Number(value || 0));
const date = (value) => new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));

function Button({ children, variant = "primary", icon: Icon, className = "", ...props }) {
  return (
    <button className={`button button--${variant} ${className}`} {...props}>
      {Icon && <Icon size={17} />}
      {children}
    </button>
  );
}

function Empty({ icon: Icon = Archive, title, text, action }) {
  return (
    <div className="empty">
      <span className="empty__icon"><Icon size={23} /></span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}

function Modal({ title, subtitle, onClose, children, wide = false }) {
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section className={`modal ${wide ? "modal--wide" : ""}`}>
        <header className="modal__header">
          <div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
          <button className="icon-button" onClick={onClose} aria-label="Закрыть"><X size={20} /></button>
        </header>
        {children}
      </section>
    </div>
  );
}

function SearchBox({ value, onChange, placeholder = "Поиск" }) {
  return (
    <label className="search-box">
      <Search size={17} />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      {value && <button onClick={() => onChange("")}><X size={15} /></button>}
    </label>
  );
}

function StatusBadge({ status }) {
  const values = {
    uploaded: ["Загружен", "neutral"], processing: ["Обработка", "blue"], completed: ["Готов", "green"], failed: ["Ошибка", "red"],
  };
  const [label, color] = values[status] || [status, "neutral"];
  return <span className={`badge badge--${color}`}>{status === "processing" && <LoaderCircle className="spin" size={12} />}{label}</span>;
}

function Field({ label, children, hint }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>;
}

function SupplierForm({ initial, onClose, onSaved, notify }) {
  const [form, setForm] = useState(initial || { name: "", inn: "", currency: "RUB" });
  const [saving, setSaving] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setSaving(true);
    try {
      await api(initial ? `/suppliers/${initial.id}/` : "/suppliers/", { method: initial ? "PATCH" : "POST", body: form });
      notify(initial ? "Поставщик обновлён" : "Поставщик добавлен"); onSaved(); onClose();
    } catch (error) { notify(error.message, "error"); } finally { setSaving(false); }
  };
  return <Modal title={initial ? "Редактировать поставщика" : "Новый поставщик"} onClose={onClose}>
    <form onSubmit={submit} className="form">
      <Field label="Название"><input required autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
      <div className="form-grid">
        <Field label="ИНН" hint="10 цифр для юрлица, 12 — для ИП"><input required inputMode="numeric" value={form.inn} onChange={(e) => setForm({ ...form, inn: e.target.value.replace(/\D/g, "") })} /></Field>
        <Field label="Валюта"><select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}><option>RUB</option><option>USD</option><option>EUR</option><option>CNY</option></select></Field>
      </div>
      <footer className="modal__actions"><Button type="button" variant="ghost" onClick={onClose}>Отмена</Button><Button disabled={saving}>{saving ? "Сохраняем…" : "Сохранить"}</Button></footer>
    </form>
  </Modal>;
}

const mappingConfig = {
  price: [
    ["sku", "Артикул", false], ["name", "Наименование", true], ["price", "Цена", true], ["unit", "Ед. изм.", false],
  ],
  estimate: [
    ["sku", "Артикул", false], ["name", "Наименование", true], ["unit", "Ед. изм.", false], ["quantity", "Количество", true],
    ["material_price", "Цена материалов", false], ["installation_price", "Цена монтажа", false],
  ],
};

function ImportWizard({ type, parentId, onClose, onDone, notify }) {
  const [step, setStep] = useState("upload");
  const [file, setFile] = useState(null);
  const [estimateName, setEstimateName] = useState("");
  const [entity, setEntity] = useState(null);
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [sheet, setSheet] = useState("");
  const [headerRow, setHeaderRow] = useState(1);
  const [busy, setBusy] = useState(false);
  const isPrice = type === "price";
  const base = isPrice ? "/price-lists" : "/estimates";

  const loadPreview = async (created = entity, selectedSheet = sheet, row = headerRow) => {
    setBusy(true);
    try {
      const data = await api(`${base}/${created.id}/preview/${query({ sheet_name: selectedSheet, header_row: row })}`);
      setPreview(data); setSheet(data.sheet_name); setStep("mapping");
    } catch (error) { notify(error.message, "error"); } finally { setBusy(false); }
  };

  const upload = async (e) => {
    e.preventDefault(); if (!file) return;
    setBusy(true);
    const data = new FormData(); data.append("file", file);
    data.append(isPrice ? "supplier" : "project", parentId);
    if (!isPrice) data.append("name", estimateName || file.name.replace(/\.[^.]+$/, ""));
    try {
      const created = await api(`${base}/`, { method: "POST", body: data }); setEntity(created); await loadPreview(created, "", 1);
    } catch (error) { notify(error.message, "error"); setBusy(false); }
  };

  const parse = async () => {
    const missing = mappingConfig[type].filter(([, , required]) => required).filter(([key]) => mapping[key] === undefined || mapping[key] === "");
    if (missing.length) { notify("Выберите обязательные колонки", "error"); return; }
    setBusy(true);
    try {
      const result = await api(`${base}/${entity.id}/parse/`, { method: "POST", body: { sheet_name: sheet, header_row: Number(headerRow), column_mapping: mapping } });
      setEntity(result); setStep("progress");
    } catch (error) { notify(error.message, "error"); } finally { setBusy(false); }
  };

  useEffect(() => {
    if (step !== "progress" || !entity) return undefined;
    const timer = setInterval(async () => {
      try {
        const fresh = await api(`${base}/${entity.id}/`); setEntity(fresh);
        if (["completed", "failed"].includes(fresh.status)) clearInterval(timer);
      } catch { /* следующий тик повторит запрос */ }
    }, 1200);
    return () => clearInterval(timer);
  }, [step, entity?.id]);

  const finish = () => { onDone(); onClose(); };
  return <Modal wide title={isPrice ? "Загрузка прайс-листа" : "Загрузка сметы"} subtitle="Excel → настройка колонок → фоновый импорт" onClose={onClose}>
    <div className="steps"><span className={step === "upload" ? "active" : "done"}>1. Файл</span><span className={step === "mapping" ? "active" : step === "progress" ? "done" : ""}>2. Колонки</span><span className={step === "progress" ? "active" : ""}>3. Импорт</span></div>
    {step === "upload" && <form onSubmit={upload} className="form">
      {!isPrice && <Field label="Название сметы"><input value={estimateName} onChange={(e) => setEstimateName(e.target.value)} placeholder="Например, Электромонтажные работы" /></Field>}
      <label className={`dropzone ${file ? "dropzone--selected" : ""}`}>
        <input type="file" accept=".xlsx,.xls" onChange={(e) => setFile(e.target.files[0])} />
        {file ? <><FileSpreadsheet size={30} /><strong>{file.name}</strong><span>{money(file.size / 1024)} КБ</span></> : <><Upload size={30} /><strong>Выберите Excel-файл</strong><span>.xlsx или .xls, до 20 МБ</span></>}
      </label>
      <footer className="modal__actions"><Button type="button" variant="ghost" onClick={onClose}>Отмена</Button><Button disabled={!file || busy} icon={Upload}>{busy ? "Читаем файл…" : "Загрузить и настроить"}</Button></footer>
    </form>}
    {step === "mapping" && preview && <div>
      <div className="mapping-toolbar">
        <Field label="Лист"><select value={sheet} onChange={(e) => setSheet(e.target.value)}>{preview.sheet_names.map((name) => <option key={name}>{name}</option>)}</select></Field>
        <Field label="Строка заголовка"><input type="number" min="1" value={headerRow} onChange={(e) => setHeaderRow(e.target.value)} /></Field>
        <Button variant="secondary" onClick={() => loadPreview(entity, sheet, headerRow)} disabled={busy}>Обновить превью</Button>
      </div>
      <div className="mapping-grid">{mappingConfig[type].map(([key, label, required]) => <Field key={key} label={`${label}${required ? " *" : ""}`}><select value={mapping[key] ?? ""} onChange={(e) => setMapping({ ...mapping, [key]: e.target.value })}><option value="">Не выбрано</option>{preview.columns.map((column) => <option key={column.index} value={column.index}>{column.label}</option>)}</select></Field>)}</div>
      <div className="preview-table table-scroll"><table><thead><tr>{preview.columns.map((column) => <th key={column.index}>{column.label}</th>)}</tr></thead><tbody>{preview.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{String(cell ?? "")}</td>)}</tr>)}</tbody></table></div>
      <footer className="modal__actions"><Button variant="ghost" onClick={onClose}>Отмена</Button><Button onClick={parse} disabled={busy} icon={Sparkles}>{busy ? "Запускаем…" : "Запустить импорт"}</Button></footer>
    </div>}
    {step === "progress" && entity && <div className="progress-screen">
      <span className={`progress-screen__icon ${entity.status === "failed" ? "error" : entity.status === "completed" ? "success" : ""}`}>{entity.status === "failed" ? <CircleAlert /> : entity.status === "completed" ? <Check /> : <LoaderCircle className="spin" />}</span>
      <h3>{entity.status === "completed" ? "Импорт завершён" : entity.status === "failed" ? "Не удалось импортировать файл" : "Разбираем строки в фоне"}</h3>
      <p>{entity.status === "failed" ? entity.error_message : `${entity.rows_processed || 0} из ${entity.rows_total || "…"} строк`}</p>
      <div className="progress"><i style={{ width: `${entity.progress}%` }} /></div><strong>{entity.progress}%</strong>
      {entity.status === "completed" && <Button onClick={finish}>Готово</Button>}
      {entity.status === "failed" && <Button variant="secondary" onClick={() => setStep("mapping")}>Проверить настройки</Button>}
    </div>}
  </Modal>;
}

function PriceItems({ priceList, onClose }) {
  const [items, setItems] = useState([]); const [loading, setLoading] = useState(true);
  useEffect(() => { api(`/supplier-items/${query({ price_list: priceList.id, page_size: 250 })}`).then((d) => setItems(rows(d))).finally(() => setLoading(false)); }, [priceList.id]);
  return <Modal wide title={priceList.original_name} subtitle={`Позиции прайс-листа · ${priceList.supplier_name}`} onClose={onClose}>
    <div className="table-scroll modal-table"><table><thead><tr><th>#</th><th>Артикул</th><th>Наименование</th><th>Ед.</th><th className="number">Цена</th><th>Каталог</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td className="muted">{item.row_number}</td><td className="mono">{item.sku || "—"}</td><td>{item.name}</td><td>{item.unit || "—"}</td><td className="number"><strong>{item.price ? money(item.price) : "—"}</strong></td><td>{item.catalog_product_detail ? <span className="badge badge--green"><Check size={12} />{item.catalog_product_detail.sku}</span> : <span className="muted">Не привязан</span>}</td></tr>)}</tbody></table>{loading && <div className="loading-row"><LoaderCircle className="spin" /> Загружаем позиции…</div>}</div>
  </Modal>;
}

function SuppliersPage({ notify }) {
  const [suppliers, setSuppliers] = useState([]); const [search, setSearch] = useState(""); const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(undefined); const [wizard, setWizard] = useState(false); const [priceLists, setPriceLists] = useState([]); const [viewPrice, setViewPrice] = useState(null);
  const load = async () => { const data = rows(await api(`/suppliers/${query({ search, page_size: 200 })}`)); setSuppliers(data); if (selected) setSelected(data.find((x) => x.id === selected.id) || data[0] || null); else if (data.length) setSelected(data[0]); };
  const loadPrices = async () => { if (selected) setPriceLists(rows(await api(`/price-lists/${query({ supplier: selected.id, page_size: 200 })}`))); };
  useEffect(() => { const timer = setTimeout(() => load().catch((e) => notify(e.message, "error")), 200); return () => clearTimeout(timer); }, [search]);
  useEffect(() => { loadPrices().catch((e) => notify(e.message, "error")); }, [selected?.id]);
  const remove = async (supplier) => { if (!confirm(`Удалить поставщика «${supplier.name}» и его прайс-листы?`)) return; await api(`/suppliers/${supplier.id}/`, { method: "DELETE" }); notify("Поставщик удалён"); setSelected(null); load(); };
  return <div className="page split-page">
    <section className="master-panel">
      <header className="page-title"><div><span className="eyebrow">Закупки</span><h1>Поставщики</h1></div><Button icon={Plus} onClick={() => setForm(null)}>Добавить</Button></header>
      <SearchBox value={search} onChange={setSearch} placeholder="Название или ИНН" />
      <div className="entity-list">{suppliers.map((supplier) => <button key={supplier.id} className={`entity-card ${selected?.id === supplier.id ? "active" : ""}`} onClick={() => setSelected(supplier)}><span className="avatar">{supplier.name.slice(0, 2).toUpperCase()}</span><span><strong>{supplier.name}</strong><small>ИНН {supplier.inn} · {supplier.currency}</small></span><em>{supplier.price_lists_count}</em><ChevronRight size={17} /></button>)}</div>
      {!suppliers.length && <Empty icon={Building2} title="Поставщиков пока нет" text="Добавьте первого поставщика, чтобы загрузить прайс." />}
    </section>
    <section className="detail-panel">{selected ? <>
      <header className="detail-header"><div><span className="eyebrow">Поставщик</span><h2>{selected.name}</h2><p>ИНН {selected.inn} · расчёты в {selected.currency}</p></div><div className="row-actions"><button className="icon-button" onClick={() => setForm(selected)}><Pencil size={17} /></button><button className="icon-button danger" onClick={() => remove(selected)}><Trash2 size={17} /></button></div></header>
      <div className="section-heading"><div><h3>Прайс-листы</h3><p>История загруженных цен поставщика</p></div><Button icon={Upload} onClick={() => setWizard(true)}>Загрузить прайс</Button></div>
      {priceLists.length ? <div className="table-card"><table><thead><tr><th>Файл</th><th>Дата</th><th>Статус</th><th className="number">Позиций</th><th></th></tr></thead><tbody>{priceLists.map((item) => <tr key={item.id}><td><button className="link-button" onClick={() => item.status === "completed" && setViewPrice(item)}><FileSpreadsheet size={17} /><span><strong>{item.original_name}</strong><small>{item.sheet_name || "Лист не выбран"}</small></span></button></td><td>{date(item.created_at)}</td><td><StatusBadge status={item.status} />{item.status === "processing" && <small className="progress-label">{item.progress}%</small>}</td><td className="number">{item.items_count}</td><td><button className="icon-button danger" onClick={async () => { if (confirm("Удалить прайс-лист?")) { await api(`/price-lists/${item.id}/`, { method: "DELETE" }); loadPrices(); } }}><Trash2 size={16} /></button></td></tr>)}</tbody></table></div> : <Empty icon={FileSpreadsheet} title="Прайс-листов нет" text="Загрузите Excel и укажите назначение колонок." action={<Button icon={Upload} onClick={() => setWizard(true)}>Загрузить прайс</Button>} />}
    </> : <Empty icon={Building2} title="Выберите поставщика" text="Справа появятся его реквизиты и прайс-листы." />}</section>
    {form !== undefined && <SupplierForm initial={form} onClose={() => setForm(undefined)} onSaved={load} notify={notify} />}
    {wizard && <ImportWizard type="price" parentId={selected.id} onClose={() => setWizard(false)} onDone={() => { loadPrices(); load(); }} notify={notify} />}
    {viewPrice && <PriceItems priceList={viewPrice} onClose={() => setViewPrice(null)} />}
  </div>;
}

function ProductForm({ initial, onClose, onSaved, notify }) {
  const [form, setForm] = useState(initial || { sku: "", name: "", unit: "шт.", group: "" });
  const submit = async (e) => { e.preventDefault(); try { await api(initial ? `/products/${initial.id}/` : "/products/", { method: initial ? "PATCH" : "POST", body: form }); notify(initial ? "Товар обновлён" : "Товар добавлен"); onSaved(); onClose(); } catch (error) { notify(error.message, "error"); } };
  return <Modal title={initial ? "Редактировать товар" : "Новый товар"} onClose={onClose}><form onSubmit={submit} className="form"><div className="form-grid"><Field label="Артикул"><input required autoFocus value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} /></Field><Field label="Ед. изм."><input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} /></Field></div><Field label="Наименование"><textarea required rows="3" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field><Field label="Группа"><input value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })} placeholder="Например, Кабельная продукция" /></Field><footer className="modal__actions"><Button variant="ghost" type="button" onClick={onClose}>Отмена</Button><Button>Сохранить</Button></footer></form></Modal>;
}

function CatalogPage({ notify }) {
  const [products, setProducts] = useState([]); const [search, setSearch] = useState(""); const [form, setForm] = useState(undefined);
  const load = async () => setProducts(rows(await api(`/products/${query({ search, page_size: 250 })}`)));
  useEffect(() => { const timer = setTimeout(() => load().catch((e) => notify(e.message, "error")), 200); return () => clearTimeout(timer); }, [search]);
  return <div className="page"><header className="page-title"><div><span className="eyebrow">Номенклатура</span><h1>Каталог товаров</h1><p>Единая база для позиций поставщиков и смет</p></div><Button icon={Plus} onClick={() => setForm(null)}>Добавить товар</Button></header><div className="toolbar"><SearchBox value={search} onChange={setSearch} placeholder="Артикул, наименование или группа" /><span className="result-count">{products.length} товаров</span></div>
    {products.length ? <div className="table-card"><table><thead><tr><th>Артикул</th><th>Наименование</th><th>Ед. изм.</th><th>Группа</th><th className="number">Предложений</th><th></th></tr></thead><tbody>{products.map((product) => <tr key={product.id}><td className="mono"><strong>{product.sku}</strong></td><td>{product.name}</td><td>{product.unit || "—"}</td><td><span className="tag">{product.group || "Без группы"}</span></td><td className="number">{product.supplier_offers_count}</td><td><div className="row-actions"><button className="icon-button" onClick={() => setForm(product)}><Pencil size={16} /></button><button className="icon-button danger" onClick={async () => { if (confirm(`Удалить «${product.name}»?`)) { await api(`/products/${product.id}/`, { method: "DELETE" }); load(); } }}><Trash2 size={16} /></button></div></td></tr>)}</tbody></table></div> : <Empty icon={Boxes} title="Каталог пуст" text="Добавьте товары — они станут основой автоматического сопоставления." action={<Button icon={Plus} onClick={() => setForm(null)}>Добавить товар</Button>} />}
    {form !== undefined && <ProductForm initial={form} onClose={() => setForm(undefined)} onSaved={load} notify={notify} />}
  </div>;
}

function ProjectForm({ initial, onClose, onSaved, notify }) {
  const [form, setForm] = useState(initial || { name: "" });
  const submit = async (e) => { e.preventDefault(); try { await api(initial ? `/projects/${initial.id}/` : "/projects/", { method: initial ? "PATCH" : "POST", body: form }); notify(initial ? "Проект обновлён" : "Проект создан"); onSaved(); onClose(); } catch (error) { notify(error.message, "error"); } };
  return <Modal title={initial ? "Редактировать проект" : "Новый проект"} onClose={onClose}><form className="form" onSubmit={submit}><Field label="Название"><input autoFocus required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field><footer className="modal__actions"><Button type="button" variant="ghost" onClick={onClose}>Отмена</Button><Button>Сохранить</Button></footer></form></Modal>;
}

function MatchCell({ item, products, onChange }) {
  const confidence = Number(item.match_confidence || 0); const good = item.match_status === "matched" && confidence >= 75;
  return <div className="match-cell"><span className={`confidence confidence--${good ? "good" : "bad"}`}><i style={{ width: `${confidence}%` }} />{money(confidence)}%</span><select value={item.catalog_product || ""} onChange={(e) => onChange(item, e.target.value ? { catalog_product: Number(e.target.value), match_status: "matched" } : { match_status: "no_match" })}><option value="">Без соответствия</option>{products.map((product) => <option key={product.id} value={product.id}>{product.sku} — {product.name}</option>)}</select><small>{item.match_explanation}</small></div>;
}

function EstimateWorkspace({ estimateId, onBack, notify }) {
  const [estimate, setEstimate] = useState(null); const [items, setItems] = useState([]); const [products, setProducts] = useState([]); const [filter, setFilter] = useState(""); const [search, setSearch] = useState(""); const [matching, setMatching] = useState(false);
  const load = async () => { const [e, itemData, productData] = await Promise.all([api(`/estimates/${estimateId}/`), api(`/estimate-items/${query({ estimate: estimateId, match_status: filter, search, page_size: 250 })}`), api("/products/?page_size=250")]); setEstimate(e); setItems(rows(itemData)); setProducts(rows(productData)); };
  useEffect(() => { const timer = setTimeout(() => load().catch((e) => notify(e.message, "error")), 150); return () => clearTimeout(timer); }, [estimateId, filter, search]);
  const updateMatch = async (item, payload) => { try { const updated = await api(`/estimate-items/${item.id}/`, { method: "PATCH", body: payload }); setItems((current) => current.map((x) => x.id === item.id ? updated : x)); } catch (error) { notify(error.message, "error"); } };
  const autoMatch = async () => { setMatching(true); try { await api(`/estimates/${estimateId}/auto_match/`, { method: "POST" }); notify("Автосопоставление запущено"); setTimeout(() => { load(); setMatching(false); }, 1800); } catch (error) { notify(error.message, "error"); setMatching(false); } };
  if (!estimate) return <div className="page loading-page"><LoaderCircle className="spin" /></div>;
  return <div className="page"><button className="back-link" onClick={onBack}><ArrowLeft size={17} /> К проекту</button><header className="page-title estimate-title"><div><span className="eyebrow">Смета · {estimate.project_name}</span><h1>{estimate.name}</h1><p>{estimate.original_name} · загружена {date(estimate.created_at)}</p></div><Button icon={Bot} onClick={autoMatch} disabled={matching}>{matching ? "Сопоставляем…" : "Сопоставить автоматически"}</Button></header>
    <div className="metrics"><article><span>Позиций</span><strong>{estimate.items_count}</strong></article><article className="metric--green"><span>Сопоставлено</span><strong>{estimate.matched_count}</strong></article><article className="metric--red"><span>Без соответствия</span><strong>{estimate.unmatched_count}</strong></article><article><span>Сумма сметы</span><strong>{money(estimate.total_amount)} ₽</strong></article></div>
    <div className="toolbar"><SearchBox value={search} onChange={setSearch} placeholder="Поиск по позициям" /><div className="segmented"><button className={!filter ? "active" : ""} onClick={() => setFilter("")}>Все</button><button className={filter === "matched" ? "active" : ""} onClick={() => setFilter("matched")}>Сопоставлены</button><button className={filter === "no_match" ? "active" : ""} onClick={() => setFilter("no_match")}>Без соответствия</button></div></div>
    <div className="table-card estimate-table table-scroll"><table><thead><tr><th>#</th><th>Исходная позиция</th><th>Ед.</th><th className="number">Кол-во</th><th className="number">Материалы</th><th className="number">Монтаж</th><th>Сопоставление / уверенность</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} className={item.match_status === "matched" && Number(item.match_confidence) >= 75 ? "row--matched" : "row--unmatched"}><td className="muted">{item.row_number}</td><td><strong>{item.name}</strong><small className="mono">{item.sku || "Без артикула"}</small></td><td>{item.unit || "—"}</td><td className="number">{money(item.quantity)}</td><td className="number">{item.material_price ? `${money(item.material_price)} ₽` : "—"}</td><td className="number">{item.installation_price ? `${money(item.installation_price)} ₽` : "—"}</td><td><MatchCell item={item} products={products} onChange={updateMatch} /></td></tr>)}</tbody></table></div>
  </div>;
}

function ProjectsPage({ notify }) {
  const [projects, setProjects] = useState([]); const [selected, setSelected] = useState(null); const [estimates, setEstimates] = useState([]); const [form, setForm] = useState(undefined); const [wizard, setWizard] = useState(false); const [workspace, setWorkspace] = useState(null);
  const load = async () => { const data = rows(await api("/projects/?page_size=200")); setProjects(data); setSelected((current) => data.find((x) => x.id === current?.id) || data[0] || null); };
  const loadEstimates = async () => { if (selected) setEstimates(rows(await api(`/estimates/${query({ project: selected.id, page_size: 200 })}`))); };
  useEffect(() => { load().catch((e) => notify(e.message, "error")); }, []); useEffect(() => { loadEstimates().catch((e) => notify(e.message, "error")); }, [selected?.id]);
  if (workspace) return <EstimateWorkspace estimateId={workspace} onBack={() => { setWorkspace(null); loadEstimates(); }} notify={notify} />;
  return <div className="page split-page"><section className="master-panel"><header className="page-title"><div><span className="eyebrow">Строительство</span><h1>Проекты</h1></div><Button icon={Plus} onClick={() => setForm(null)}>Создать</Button></header><div className="entity-list">{projects.map((project) => <button key={project.id} className={`entity-card ${selected?.id === project.id ? "active" : ""}`} onClick={() => setSelected(project)}><span className="avatar avatar--project"><FolderKanban size={19} /></span><span><strong>{project.name}</strong></span><em>{project.estimates_count}</em><ChevronRight size={17} /></button>)}</div>{!projects.length && <Empty icon={FolderKanban} title="Проектов пока нет" text="Создайте проект, чтобы собирать в нём сметы." />}</section>
    <section className="detail-panel">{selected ? <><header className="detail-header"><div><span className="eyebrow">Проект</span><h2>{selected.name}</h2></div><div className="row-actions"><button className="icon-button" onClick={() => setForm(selected)}><Pencil size={17} /></button><button className="icon-button danger" onClick={async () => { if (confirm(`Удалить проект «${selected.name}»?`)) { await api(`/projects/${selected.id}/`, { method: "DELETE" }); setSelected(null); load(); } }}><Trash2 size={17} /></button></div></header><div className="section-heading"><div><h3>Сметы</h3><p>Импортированные расчёты проекта</p></div><Button icon={Upload} onClick={() => setWizard(true)}>Загрузить смету</Button></div>
      {estimates.length ? <div className="cards-grid">{estimates.map((item) => <button className="estimate-card" key={item.id} onClick={() => item.status === "completed" && setWorkspace(item.id)}><div><FileSpreadsheet size={22} /><StatusBadge status={item.status} /></div><h3>{item.name}</h3><p>{item.original_name}</p>{item.status === "processing" ? <div className="mini-progress"><i style={{ width: `${item.progress}%` }} /></div> : <dl><div><dt>Позиций</dt><dd>{item.items_count}</dd></div><div><dt>Сопоставлено</dt><dd>{item.matched_count}/{item.items_count}</dd></div><div><dt>Сумма</dt><dd>{money(item.total_amount)} ₽</dd></div></dl>}<small>{date(item.created_at)}</small></button>)}</div> : <Empty icon={FileSpreadsheet} title="Смет пока нет" text="Загрузите Excel, настройте колонки — позиции появятся здесь." action={<Button icon={Upload} onClick={() => setWizard(true)}>Загрузить смету</Button>} />}</> : <Empty icon={FolderKanban} title="Выберите проект" text="Здесь появятся его сметы и сводные показатели." />}</section>
    {form !== undefined && <ProjectForm initial={form} onClose={() => setForm(undefined)} onSaved={load} notify={notify} />}{wizard && <ImportWizard type="estimate" parentId={selected.id} onClose={() => setWizard(false)} onDone={() => { loadEstimates(); load(); }} notify={notify} />}
  </div>;
}

export default function App() {
  const [page, setPage] = useState("suppliers"); const [mobileNav, setMobileNav] = useState(false); const [toast, setToast] = useState(null);
  const notify = (message, type = "success") => { setToast({ message, type }); setTimeout(() => setToast(null), 3500); };
  const nav = [{ id: "suppliers", label: "Поставщики", icon: Building2 }, { id: "catalog", label: "Каталог", icon: Boxes }, { id: "projects", label: "Проекты и сметы", icon: FolderKanban }];
  return <div className="app-shell"><aside className={`sidebar ${mobileNav ? "sidebar--open" : ""}`}><div className="brand"><span><Sparkles size={19} /></span><div><strong>СметаХаб</strong><small>умные закупки</small></div></div><nav>{nav.map(({ id, label, icon: Icon }) => <button key={id} className={page === id ? "active" : ""} onClick={() => { setPage(id); setMobileNav(false); }}><Icon size={19} />{label}</button>)}</nav><footer><span className="ai-dot" /> Автосопоставление активно</footer></aside><main><div className="mobile-header"><button className="icon-button" onClick={() => setMobileNav(!mobileNav)}><Menu /></button><strong>СметаХаб</strong></div>{page === "suppliers" && <SuppliersPage notify={notify} />}{page === "catalog" && <CatalogPage notify={notify} />}{page === "projects" && <ProjectsPage notify={notify} />}</main>{toast && <div className={`toast toast--${toast.type}`}>{toast.type === "error" ? <CircleAlert size={18} /> : <Check size={18} />}{toast.message}</div>}</div>;
}

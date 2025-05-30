"use client";

import { useState } from "react";

interface CreateListingFormProps {
  onSubmit: (data: {
    listing_type: "request" | "offer";
    title: string;
    description: string;
    hours: number;
  }) => void;
  onCancel: () => void;
}

export default function CreateListingForm({
  onSubmit,
  onCancel,
}: CreateListingFormProps) {
  const [listingType, setListingType] = useState<"request" | "offer">("request");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [hours, setHours] = useState(1);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ listing_type: listingType, title, description, hours });
  };

  return (
    <form onSubmit={handleSubmit} className="card p-8 space-y-8 glass-card">
      <div className="space-y-4">
        <label className="block text-sm font-medium text-white/80">Тип заявки</label>
        <div className="grid grid-cols-2 gap-4">
          <button
            type="button"
            onClick={() => setListingType("request")}
            className={`btn ${
              listingType === "request"
                ? "bg-white text-black hover:bg-white/90"
                : "bg-transparent hover:bg-white/5 text-white/60 border border-white/[0.08]"
            } glass-card`}
          >
            Поиск помощи
          </button>
          <button
            type="button"
            onClick={() => setListingType("offer")}
            className={`btn ${
              listingType === "offer"
                ? "bg-white text-black hover:bg-white/90"
                : "bg-transparent hover:bg-white/5 text-white/60 border border-white/[0.08]"
            } glass-card`}
          >
            Предложение помощи
          </button>
        </div>
      </div>

      <div className="space-y-3">
        <label htmlFor="title" className="block text-sm font-medium text-white/80">
          Заголовок
        </label>
        <input
          type="text"
          id="title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="input"
          placeholder="Краткое описание заявки"
          required
        />
      </div>

      <div className="space-y-3">
        <label htmlFor="description" className="block text-sm font-medium text-white/80">
          Описание
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="input"
          rows={4}
          placeholder={
            listingType === "request"
              ? "Опишите, какая помощь вам требуется..."
              : "Опишите, какую помощь вы можете предложить..."
          }
          required
        />
      </div>

      <div className="space-y-3">
        <label htmlFor="hours" className="block text-sm font-medium text-white/80">
          Количество часов
        </label>
        <input
          type="number"
          id="hours"
          value={hours}
          onChange={(e) => setHours(Math.max(1, parseInt(e.target.value)))}
          min="1"
          className="input"
          required
        />
      </div>

      <div className="flex gap-4 pt-4">
        <button type="submit" className="btn-primary flex-1 glass-card">
          Создать
        </button>
        <button type="button" onClick={onCancel} className="btn-ghost flex-1">
          Отмена
        </button>
      </div>
    </form>
  );
} 
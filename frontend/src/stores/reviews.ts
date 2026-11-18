import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { fetchReviewCards, gradeReviewCard } from "@/api/knowledge";
import type { ReviewCard, ReviewGrade } from "@/types";

export const useReviewsStore = defineStore("reviews", () => {
  const cards = ref<ReviewCard[]>([]);
  const currentIndex = ref(0);
  const totalCount = ref(0);
  const reviewedCount = ref(0);
  const revealed = ref(false);
  const loading = ref(false);
  const grading = ref(false);

  let sessionEpoch = 0;

  const current = computed<ReviewCard | null>(() => cards.value[currentIndex.value] ?? null);
  const progressLabel = computed(() => {
    if (!totalCount.value) return "暂无待复习";
    if (!cards.value.length) return "本轮复习完成";
    return `第 ${Math.min(reviewedCount.value + 1, totalCount.value)} / ${totalCount.value} 张`;
  });

  function reset(): void {
    sessionEpoch += 1;
    cards.value = [];
    currentIndex.value = 0;
    totalCount.value = 0;
    reviewedCount.value = 0;
    revealed.value = false;
    loading.value = false;
    grading.value = false;
  }

  async function load(): Promise<void> {
    const epoch = sessionEpoch;
    loading.value = true;
    try {
      const items = await fetchReviewCards();
      if (epoch !== sessionEpoch) return;
      cards.value = items;
      currentIndex.value = 0;
      totalCount.value = items.length;
      reviewedCount.value = 0;
      revealed.value = false;
    } finally {
      if (epoch === sessionEpoch) loading.value = false;
    }
  }

  function flip(): void {
    revealed.value = true;
  }

  async function gradeCurrent(grade: ReviewGrade): Promise<ReviewCard | null> {
    const card = current.value;
    if (!card || grading.value) return null;
    grading.value = true;
    try {
      const updated = await gradeReviewCard(card.id, grade, card.version);
      cards.value = cards.value.filter((item) => item.id !== card.id);
      currentIndex.value = 0;
      reviewedCount.value += 1;
      revealed.value = false;
      return updated;
    } finally {
      grading.value = false;
    }
  }

  return {
    cards,
    currentIndex,
    totalCount,
    reviewedCount,
    current,
    progressLabel,
    revealed,
    loading,
    grading,
    load,
    flip,
    gradeCurrent,
    reset,
  };
});

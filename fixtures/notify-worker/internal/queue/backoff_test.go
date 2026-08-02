package queue

import (
	"testing"
	"time"
)

func TestBackoffIsCapped(t *testing.T) {
	if got := Backoff(20); got != time.Minute {
		t.Fatalf("got %v, want 1m", got)
	}
}

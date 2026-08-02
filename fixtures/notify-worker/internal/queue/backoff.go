package queue

import "time"

// Backoff returns the delay before retry n, capped at one minute.
func Backoff(n int) time.Duration {
	d := time.Duration(1<<uint(n)) * time.Second
	if d > time.Minute {
		return time.Minute
	}
	return d
}

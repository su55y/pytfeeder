package main

import (
	"bytes"
	"cmp"
	"flag"
	"fmt"
	"html"
	"os"
	"regexp"
	"slices"
	"sort"
	"strconv"
	"strings"
	"text/template"

	"github.com/lestrrat-go/strftime"

	"github.com/su55y/pytfeeder/examples/go-ytfeeder-rofi/internal/config"
	"github.com/su55y/pytfeeder/examples/go-ytfeeder-rofi/internal/models"
	"github.com/su55y/pytfeeder/examples/go-ytfeeder-rofi/internal/storage"
)

var (
	configPath     string
	printConfig    bool
	channelId      string
	channelsFmt    string
	feedEntriesFmt string
	entriesFmt     string
	datetimeFmt    string
)

func parseArgs() {
	flag.StringVar(
		&configPath,
		"c",
		config.DefaultConfigPath(),
		"Config filepath",
	)
	flag.StringVar(
		&channelsFmt,
		"channels-fmt",
		"",
		fmt.Sprintf("Channels format (default %#+v)", config.DefaultChannelsFmt),
	)
	flag.StringVar(
		&feedEntriesFmt,
		"feed-entries-fmt",
		"",
		fmt.Sprintf("Feed entries format (default %#+v)", config.DefaultFeedEntriesFmt),
	)
	flag.StringVar(
		&entriesFmt,
		"entries-fmt",
		"",
		fmt.Sprintf("Entries format (default %#+v)", config.DefaultEntriesFmt),
	)
	flag.StringVar(
		&datetimeFmt,
		"datetime-fmt",
		"",
		fmt.Sprintf("Datetime format (default %#+v)", config.DefaultDatetimeFmt),
	)
	flag.StringVar(&channelId, "i", "", "Channel id")
	flag.BoolVar(&printConfig, "p", false, "Print config and exit")
	flag.Parse()
}

func unescapeFmt(f string) string {
	unescaped, err := strconv.Unquote(`"` + f + `"`)
	if err != nil {
		fmt.Printf("ERR: %v\n", err)
		os.Exit(1)
	}
	return unescaped
}

func main() {
	parseArgs()
	c := config.GetConfig(configPath)
	if printConfig {
		c.Print()
		os.Exit(0)
	}

	stor := storage.NewStorage(c.StorageFile)

	if channelsFmt != "" {
		c.ChannelsFmt = unescapeFmt(channelsFmt)
	}
	if datetimeFmt != "" {
		c.DatetimeFmt = datetimeFmt
	}
	if feedEntriesFmt != "" {
		c.FeedEntriesFmt = unescapeFmt(feedEntriesFmt)
	}
	if entriesFmt != "" {
		c.EntriesFmt = unescapeFmt(entriesFmt)
	}

	selectStats := strings.Contains(c.ChannelsFmt, "{total}") ||
		strings.Contains(c.ChannelsFmt, "{unwatched}") ||
		strings.Contains(c.ChannelsFmt, "{unwatched_total}")

	channels := config.LoadChannels(c.ChannelsPath)
	if c.AlphabeticSort {
		sort.Slice(channels, func(i, j int) bool {
			return strings.ToLower(channels[i].Title) < strings.ToLower(channels[j].Title)
		})
	}

	if !c.HideFeed {
		feedChannel := models.Channel{Id: "feed", Title: "Feed"}
		if selectStats {
			err := stor.SelectFeedStats(&feedChannel, channels)
			if err != nil {
				fmt.Printf("ERR: %v\n", err)
				os.Exit(1)
			}
		}
		channels = slices.Insert(channels, 0, feedChannel)
	}

	tplRe := regexp.MustCompile(`\{([a-z_]+)\}`)

	channelsMap := make(map[string]*models.Channel)
	for i := range channels {
		channelsMap[channels[i].Id] = &channels[i]
	}

	if channelId == "" {
		fmt.Printf("\000data\037main%s", c.Separator.Value)
		if selectStats {
			if err := stor.SelectChannelsStats(channelsMap); err != nil {
				fmt.Printf("ERR: %v\n", err)
				os.Exit(1)
			}
		}

		tmplStr := tplRe.ReplaceAllString(c.ChannelsFmt+c.Separator.Value, `{{.$1}}`)
		tmpl, err := template.New("channel_fmt").Parse(tmplStr)
		if err != nil {
			panic(err)
		}

		numWidth := len(strconv.Itoa(slices.MaxFunc(channels, func(a, b models.Channel) int {
			return cmp.Compare(a.Total, b.Total)
		}).Total))

		for _, ch := range channels {
			if ch.Hidden || (ch.Total == 0 && c.HideEmpty) {
				continue
			}
			d := map[string]any{
				"id":        ch.Id,
				"title":     html.EscapeString(ch.Title),
				"total":     ch.Total,
				"unwatched": ch.Unwatched,
				"unwatched_total": fmt.Sprintf(
					"%*d/%*d",
					numWidth,
					ch.Unwatched,
					numWidth,
					ch.Total,
				),
				"active": fmt.Sprintf("%t", ch.HaveUpdates),
			}
			if err := tmpl.Execute(os.Stdout, d); err != nil {
				fmt.Printf("ERR: tmpl.Execute: %#+v (%#+v)\n", err, d)
			}
		}

		os.Exit(0)
	}

	if channelId != "feed" && len(channelId) != 24 {
		fmt.Printf("Invalid channel_id %#+v%s", channelId, c.Separator.Value)
		os.Exit(1)
	}

	limit := c.ChannelFeedLimit
	f := c.EntriesFmt + c.Separator.Value
	if channelId == "feed" {
		limit = c.FeedLimit
		f = c.FeedEntriesFmt + c.Separator.Value
	}

	timeFormatter, strftimeErr := strftime.New(c.DatetimeFmt)
	if strftimeErr != nil {
		fmt.Printf("ERR: %v (%#+v)\n", strftimeErr, c.DatetimeFmt)
		os.Exit(1)
	}

	tmplStr := tplRe.ReplaceAllString(f, `{{.$1}}`)
	tmpl, err := template.New("entries_fmt").Parse(tmplStr)
	if err != nil {
		panic(err)
	}

	entries, err := stor.SelectEntries(channelId, c.UnwatchedFirst, limit, channels)
	if err != nil {
		fmt.Printf("ERR: %v%s", channelId, c.Separator.Value)
		os.Exit(1)
	}

	fmt.Printf("\000data\037%s%s", channelId, c.Separator.Value)
	for _, e := range entries {
		channelTitle := "Unknown"
		if c, ok := channelsMap[e.ChannelId]; ok {
			channelTitle = c.Title
		}

		published := bytes.NewBufferString("")
		_ = timeFormatter.Format(published, e.Published)

		m := map[string]string{
			"id":            e.Id,
			"title":         html.EscapeString(e.Title),
			"channel_title": html.EscapeString(channelTitle),
			"published":     published.String(),
			"active":        fmt.Sprintf("%t", !e.IsViewed),
		}
		if err := tmpl.Execute(os.Stdout, m); err != nil {
			fmt.Printf("ERR: tmpl.Execute: %#+v (%#+v)\n", err, m)
		}
	}
}

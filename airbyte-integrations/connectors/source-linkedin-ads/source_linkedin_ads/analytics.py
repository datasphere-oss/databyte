#
# MIT License
#
# Copyright (c) 2020 Airbyte
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#


from typing import Any, Dict, Iterable, List, Mapping

import pendulum as pdm

from .utils import make_slice

# LinkedIn has a max of 20 fields per request. We make chunks by 17
# to make sure there's always room for `dateRange`, `pivot`, and `pivotValue`
FIELDS_CHUNK_SIZE = 17
WINDOW_IN_DAYS = 30

# List of adAnalyticsV2 fields available for fetch
ANALYTICS_FIELDS_V2: Dict = [
    "actionClicks",
    "adUnitClicks",
    "approximateUniqueImpressions",
    "cardClicks",
    "cardImpressions",
    "clicks",
    "commentLikes",
    "comments",
    "companyPageClicks",
    "conversionValueInLocalCurrency",
    "costInLocalCurrency",
    "costInUsd",
    "dateRange",
    "externalWebsiteConversions",
    "externalWebsitePostClickConversions",
    "externalWebsitePostViewConversions",
    "follows",
    "fullScreenPlays",
    "impressions",
    "landingPageClicks",
    "leadGenerationMailContactInfoShares",
    "leadGenerationMailInterestedClicks",
    "likes",
    "oneClickLeadFormOpens",
    "oneClickLeads",
    "opens",
    "otherEngagements",
    "pivot",
    "pivotValue",
    "pivotValues",
    "reactions",
    "sends",
    "shares",
    "textUrlClicks",
    "totalEngagements",
    "videoCompletions",
    "videoFirstQuartileCompletions",
    "videoMidpointCompletions",
    "videoStarts",
    "videoThirdQuartileCompletions",
    "videoViews",
    "viralCardClicks",
    "viralCardImpressions",
    "viralClicks",
    "viralCommentLikes",
    "viralComments",
    "viralCompanyPageClicks",
    "viralExternalWebsiteConversions",
    "viralExternalWebsitePostClickConversions",
    "viralExternalWebsitePostViewConversions",
    "viralFollows",
    "viralFullScreenPlays",
    "viralImpressions",
    "viralLandingPageClicks",
    "viralLikes",
    "viralOneClickLeadFormOpens",
    "viralOneClickLeads",
    "viralOtherEngagements",
    "viralReactions",
    "viralShares",
    "viralTotalEngagements",
    "viralVideoCompletions",
    "viralVideoFirstQuartileCompletions",
    "viralVideoMidpointCompletions",
    "viralVideoStarts",
    "viralVideoThirdQuartileCompletions",
    "viralVideoViews",
]

BASE_ANALLYTICS_FIELDS = ["dateRange", "pivot", "pivotValue"]


def chunk_analytics_fields(fields: List = ANALYTICS_FIELDS_V2, fields_chunk_size: int = FIELDS_CHUNK_SIZE) -> Iterable[Mapping]:
    """
    Chunks the list of available fields into the chunks of equal size.
    #TODO: make and example of the output.
    """
    # Define base fields that should be present by default
    base_fields = BASE_ANALLYTICS_FIELDS
    # Make chunks
    chunks = list((fields[f : f + fields_chunk_size] for f in range(0, len(fields), fields_chunk_size)))
    # Make sure base_fields are within the chunks
    for chunk in chunks:
        for field in base_fields:
            if field not in chunk:
                chunk.append(field)
    return chunks


def make_date_slices(start_date: str, window_in_days: int = WINDOW_IN_DAYS, end_date: str = None) -> Iterable[Mapping]:
    """
    Produces date slices from start_date to end_date (if specified), otherwise end_date will be present time.
    """
    start = pdm.parse(start_date)
    end = pdm.parse(end_date) if end_date else pdm.now()
    date_slices = []
    while start < end:
        slice_end_date = start.add(days=window_in_days)
        date_slice = {
            "start.day": start.day,
            "start.month": start.month,
            "start.year": start.year,
            "end.day": slice_end_date.day,
            "end.month": slice_end_date.month,
            "end.year": slice_end_date.year,
        }
        date_slices.append({"dateRange": date_slice})
        start = slice_end_date if slice_end_date <= end else end
    return date_slices


def make_analytics_slices(records: List, key_value_map: Dict, start_date: str) -> Iterable[Mapping]:
    """
    We drive the ability to directly pass the prepared parameters inside the stream_slice.
    The output of this method is ready slices for analytics streams:
    """
    # define the base_slice
    base_slice = make_slice(records, key_value_map)
    # add chunked fields, date_slices to the base_slice
    analytics_slices = []
    for fields_set in chunk_analytics_fields():
        base_slice.update(**{"fields": ",".join(map(str, fields_set))})
        for date_slice in make_date_slices(start_date):
            base_slice.update(**date_slice)
            analytics_slices.append(base_slice.copy())
    return analytics_slices


def update_analytics_params(stream_slice: Dict) -> Mapping[str, Any]:
    """
    Produces the date range parameters from input stream_slice
    """
    return {
        # Start date range
        "dateRange.start.day": stream_slice["dateRange"]["start.day"],
        "dateRange.start.month": stream_slice["dateRange"]["start.month"],
        "dateRange.start.year": stream_slice["dateRange"]["start.year"],
        # End date range
        "dateRange.end.day": stream_slice["dateRange"]["end.day"],
        "dateRange.end.month": stream_slice["dateRange"]["end.month"],
        "dateRange.end.year": stream_slice["dateRange"]["end.year"],
        # Chunk of fields
        "fields": stream_slice["fields"],
    }


def merge_chunks(chunked_result: Iterable[Mapping[str, Any]], merge_by_key: str) -> Iterable[Mapping]:
    """
    We need to merge the chunked API responses into the single structure using any available unique field.
    """
    # Merge the pieces together
    merged = {}
    for chunk in chunked_result:
        for key in chunk:
            head_key = key[merge_by_key]
            if head_key in merged:
                merged[head_key].update(key)
            else:
                merged[head_key] = key
    # Clean up the result by getting out the values of the merged keys
    result = []
    for key in merged:
        result.append(merged.get(key))
    return result
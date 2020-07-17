from tdda import rexpy


def infer_regex(items: list):
    """
    Infers the best regex string for matching the items in a list
    :param items: the items to infer the regex from
    :return: the regex string
    """
    extractor = rexpy.Extractor(items)
    extractor.batch_extract(items)
    results: rexpy.ResultsSummary = extractor.results
    return results.rex


if __name__ == '__main__':
    x = infer_regex(['Report 4 Health',
                     'Report 3 Health',
                     'Report 2 Takeout',
                     'Report 2 Health',
                     'C9ORF033_13',
                     'GRN271_11',
                     'GRN274_11',
                     "Population",
                     'C9ORF033_12'])
    print(x)

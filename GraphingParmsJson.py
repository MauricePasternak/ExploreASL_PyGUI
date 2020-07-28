import pandas as pd
import json

d = \
    {
        "Relational Gridplot": {
            "Figure Type": "Grid",
            "standard args": {
                "x": {
                    "name": "X-axis Variable",
                    "dtype": ["float", "float16", "float32", "float64", "int", "int8", "int16", "int32", "int64"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "y": {
                    "name": "Y-axis Variable",
                    "dtype": ["float", "float16", "float32", "float64", "int", "int8", "int16", "int32", "int64"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "hue": {
                    "name": "Hue Grouping Variable",
                    "dtype": ["object", "category", "bool", "float", "float16", "float32", "float64", "int", "int8",
                              "int16", "int32", "int64"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "style": {
                    "name": "Style Grouping Variable",
                    "dtype": ["object", "category", "bool", "float", "float16", "float32", "float64", "int", "int8",
                              "int16", "int32", "int64"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "row": {
                    "name": "Row Grouping Variable",
                    "dtype": ["object", "category"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "col": {
                    "name": "Column Grouping Variable",
                    "dtype": ["object", "category"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "legend": {
                    "name": "Legend",
                    "dtype": None,
                    "widget": "combobox",
                    "default": [
                        "Brief Description",
                        "Full Description",
                        "No Legend"
                    ],
                    "translator": {
                        "Brief Description": "brief",
                        "Full Description": "full",
                        "No Legend": False
                    }
                },
                "kind": {
                    "name": "Underlying Plot Type",
                    "dtype": None,
                    "widget": "combobox",
                    "default": [
                        "Scatterplot",
                        "Lineplot"
                    ],
                    "translator": {
                        "Scatterplot": "scatter",
                        "Lineplot": "line"
                    }
                },
                "height": {
                    "name": "Height of each Facet (inches)",
                    "dtype": None,
                    "widget": "doublespinbox",
                    "default": 5,
                    "min": 1,
                    "max": 20,
                    "step": 0.01
                },
                "aspect": {
                    "name": "Figure aspect ratio",
                    "dtype": None,
                    "widget": "doublespinbox",
                    "default": 1,
                    "min": 0.1,
                    "max": 20,
                    "step": 0.01
                }
            },
            "other args": {
                "facet_kws": {
                    "type": "nested",
                    "args": {
                        "sharex": {
                            "name": "Share X axis ranges",
                            "dtype": None,
                            "widget": "checkbox",
                            "default": True
                        },
                        "sharey": {
                            "name": "Share Y axis ranges",
                            "dtype": None,
                            "widget": "checkbox",
                            "default": True
                        },
                        "margin_titles": {
                            "name": "Place facet titles along margins?",
                            "dtype": None,
                            "widget": "checkbox",
                            "default": True,
                        }
                    }
                }
            }
        },
        "Categorical Gridplot": {
            "Figure Type": "Grid",
            "standard args": {
                "x": {
                    "name": "X-axis Variable",
                    "dtype": ["object", "category", "bool"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "y": {
                    "name": "Y-axis Variable",
                    "dtype": ["object", "category", "bool", "float", "float16", "float32", "float64", "int", "int8",
                              "int16", "int32", "int64"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "hue": {
                    "name": "Hue Grouping Variable",
                    "dtype": ["object", "category", "bool", "float", "float16", "float32", "float64", "int", "int8",
                              "int16", "int32", "int64"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "row": {
                    "name": "Row Grouping Variable",
                    "dtype": ["object", "category"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "col": {
                    "name": "Column Grouping Variable",
                    "dtype": ["object", "category"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "ci": {
                    "name": "Error bar basis",
                    "dtype": None,
                    "widget": "combobox",
                    "clear_btn": False,
                    "default": [
                        "95% Confidence Interval",
                        "Standard Deviation",
                        "Omit Error Bars"
                    ],
                    "translator": {
                        "95% Confidence Interval": 0.95,
                        "Standard Deviation": 'sd',
                        "Omit Error Bars": None
                    }
                },
                "kind": {
                    "name": "Underlying Plot Type",
                    "dtype": None,
                    "widget": "combobox",
                    "default": [
                        "Point Plot",
                        "Bar Plot",
                        "Strip Plot",
                        "Swarm Plot",
                        "Box Plot",
                        "Violin Plot",
                        "Boxen Plot"
                    ],
                    "translator": {
                        "Point Plot": "point",
                        "Bar Plot": "bar",
                        "Strip Plot": "strip",
                        "Swarm Plot": "swarm",
                        "Box Plot": "box",
                        "Violin Plot": "violin",
                        "Boxen Plot": "boxen"
                    }
                },
                "height": {
                    "name": "Height of each Facet (inches)",
                    "dtype": None,
                    "widget": "doublespinbox",
                    "default": 5,
                    "min": 1,
                    "max": 20,
                    "step": 0.01
                },
                "aspect": {
                    "name": "Figure aspect ratio",
                    "dtype": None,
                    "widget": "doublespinbox",
                    "default": 1,
                    "min": 0.1,
                    "max": 20,
                    "step": 0.01
                },
                "margin_titles": {
                    "name": "Place facet titles along margins?",
                    "dtype": None,
                    "widget": "checkbox",
                    "default": True,
                }
            },
            "other args": {
                "facet_kws": {
                    "type": "nested",
                    "args": {
                        "sharex": {
                            "name": "Share X axis ranges",
                            "dtype": None,
                            "widget": "checkbox",
                            "default": True
                        },
                        "sharey": {
                            "name": "Share Y axis ranges",
                            "dtype": None,
                            "widget": "checkbox",
                            "default": True
                        },
                        "margin_titles": {
                            "name": "Place facet titles along margins?",
                            "dtype": None,
                            "widget": "checkbox",
                            "default": True,
                        }
                    }
                }
            }
        },
        "Linear Models Gridplot": {
            "Figure Type": "Grid",
            "standard args": {
                "x": {
                    "name": "X-axis Variable",
                    "dtype": ["float", "float16", "float32", "float64", "int", "int8", "int16", "int32", "int64"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "y": {
                    "name": "Y-axis Variable",
                    "dtype": ["float", "float16", "float32", "float64", "int", "int8", "int16", "int32", "int64"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "hue": {
                    "name": "Hue Grouping Variable",
                    "dtype": ["object", "category", "bool"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "row": {
                    "name": "Row Grouping Variable",
                    "dtype": ["object", "category"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "col": {
                    "name": "Column Grouping Variable",
                    "dtype": ["object", "category"],
                    "widget": "d&d_lineedit",
                    "default": ""
                },
                "fit_reg": {
                    "name": "Fit a regression model?",
                    "dtype": None,
                    "widget": "checkbox",
                    "default": True
                },
                "ci": {
                    "name": "Error margins basis",
                    "dtype": None,
                    "widget": "combobox",
                    "clear_btn": False,
                    "default": [
                        "95% Confidence Interval",
                        "90% Confidence Interval",
                        "99% Confidence Interval",
                        "Omit Modelling Error"
                    ],
                    "translator": {
                        "95% Confidence Interval": 95,
                        "90% Confidence Interval": 90,
                        "99% Confidence Interval": 99,
                        "Omit Modelling Error": None
                    }
                },
                "order": {
                    "name": "Polynomial Power of the Regression Line",
                    "dtype": None,
                    "widget": "spinbox",
                    "default": 1,
                    "min": 1,
                    "max": 4,
                    "step": 1
                },
                "truncate": {
                    "name": "Limit the model to the range of the data?",
                    "dtype": None,
                    "widget": "checkbox",
                    "default": False
                },
                "height": {
                    "name": "Height of each Facet (inches)",
                    "dtype": None,
                    "widget": "doublespinbox",
                    "default": 5,
                    "min": 1,
                    "max": 20,
                    "step": 0.01
                },
                "aspect": {
                    "name": "Figure aspect ratio",
                    "dtype": None,
                    "widget": "doublespinbox",
                    "default": 1,
                    "min": 0.1,
                    "max": 20,
                    "step": 0.01
                },
            }
        }
    }

with open("ExploreASL_GUI\\xASL_GUI_GraphSettings.json", 'w') as w:
    json.dump(d, w, indent=2)

root = r'C:\Users\Maurice\Documents\GENFI\3D_Spiral\analysis\Population\Stats\mean_qCBF_StandardSpace_MNI_structural_n=41_12-Jun-2020_PVC0.tsv'
df = pd.read_csv(root, sep='\t')
df.drop(0, inplace=True)
df["Thalamus_R"] = df["Thalamus_R"].astype("float16")
print(df.dtypes)

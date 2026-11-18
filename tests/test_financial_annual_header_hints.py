import unittest
from scripts.financial_annual_header_hints import annual_header_hints


def cell(text, row, col, x0, x1, page=1, table=0):
    return {'text':text,'row_index':row,'column_index':col,'page':page,'table_index':table,
            'bbox':[x0,row*20,x1,row*20+10]}


class AnnualHeaderTests(unittest.TestCase):
    def test_multi_year_and_restatement_chain_keep_explicit_evidence(self):
        cells=[cell('2025 年',0,0,0,100),cell('2024年',0,1,100,300),
               cell('调整前',1,1,100,200),cell('调整后',1,2,200,300),
               cell('101.00',2,0,10,90),cell('90.00',2,1,110,190),cell('89.00',2,2,210,290)]
        r=annual_header_hints(cells)
        self.assertEqual(r['hint_count'],3)
        self.assertEqual([c['year_hint_unverified'] for c in r['candidates']],[2025,2024,2024])
        self.assertEqual([c['restatement_hint_unverified'] for c in r['candidates']],
                         [None,'before_adjustment','after_adjustment'])
        self.assertEqual(r['candidates'][2]['restatement_header_cell']['text'],'调整后')
        self.assertFalse(r['financial_meaning_verified'])

    def test_year_end_block_replaces_earlier_annual_header(self):
        r=annual_header_hints([cell('2025年',0,0,0,100),cell('10',1,0,10,90),
                              cell('2025年末',2,0,0,100),cell('20',3,0,10,90)])
        self.assertEqual([c['basis_hint_unverified'] for c in r['candidates']],['annual','year_end'])

    def test_quarter_or_unknown_header_blocks_old_year(self):
        for label in ('第一季度','其他表格'):
            r=annual_header_hints([cell('2025年',0,0,0,100),cell('10',1,0,10,90),
                                  cell(label,2,0,0,100),cell('20',3,0,10,90)])
            self.assertEqual(r['candidates'][0]['year_hint_unverified'],2025)
            self.assertIsNone(r['candidates'][1]['year_hint_unverified'])

    def test_no_cross_page_table_or_horizontal_center_guess(self):
        for number in (cell('10',1,0,10,90,page=2),cell('10',1,0,10,90,table=1),
                       cell('10',1,0,90,110)):
            r=annual_header_hints([cell('2025年',0,0,0,100),number])
            self.assertIsNone(r['candidates'][0]['year_hint_unverified'])

    def test_ambiguous_year_or_child_stays_unknown(self):
        for headers in ([cell('2025年',0,0,0,100),cell('2024年',0,1,0,100)],
                        [cell('2025年',0,0,0,100),cell('调整前',1,0,0,100),cell('调整后',1,1,0,100)],
                        [cell('2025年',0,0,0,100),cell('调整前',1,0,0,40)]):
            r=annual_header_hints(headers+[cell('10',2,0,50,90)])
            self.assertIsNone(r['candidates'][0]['year_hint_unverified'])

    def test_duplicate_invalid_bounds_and_geometry_rejected(self):
        c=cell('10',1,0,10,90)
        for data in ([c,c],[cell('10',500,0,10,90)], [{**c,'bbox':[90,1,10,2]}]):
            with self.assertRaises(ValueError):
                annual_header_hints(data)

class NarrowRestatementHeaderTests(unittest.TestCase):
    def fixture(self):
        return [cell('2024年',0,0,0,200),cell('调整前',1,0,20,80),
                cell('调整后',1,1,120,180),cell('100.00',2,0,0,100),cell('99.00',2,1,100,200)]

    def test_two_number_rectangles_tile_year_with_unique_narrow_labels(self):
        r=annual_header_hints(self.fixture())
        self.assertEqual(r['hint_count'],2)
        self.assertEqual([c['restatement_hint_unverified'] for c in r['candidates']],
                         ['before_adjustment','after_adjustment'])
        self.assertTrue(all(c['reason']=='explicit_restatement_row_partition_unverified' for c in r['candidates']))
        self.assertEqual(len(r['candidates'][0]['partition_cells_unverified']),2)
        self.assertFalse(r['column_ownership_verified'])

    def test_gaps_overlap_missing_half_and_parent_edge_mismatch_block(self):
        for index,box in ((3,[1,40,100,50]),(3,[0,40,99,50]),(3,[0,40,101,50]),(4,[101,40,200,50])):
            cells=self.fixture();cells[index]['bbox']=box
            self.assertEqual(annual_header_hints(cells)['hint_count'],0)
        cells=self.fixture();cells.pop()
        self.assertEqual(annual_header_hints(cells)['hint_count'],0)

    def test_straddling_duplicate_or_crossing_labels_block(self):
        for box in ([80,20,120,30],[-10,20,80,30],[20,39,80,45]):
            cells=self.fixture();cells[1]['bbox']=box
            self.assertEqual(annual_header_hints(cells)['hint_count'],0)
        cells=self.fixture();cells[2]['text']='调整前'
        self.assertEqual(annual_header_hints(cells)['hint_count'],0)

    def test_three_value_columns_cannot_use_two_column_partition(self):
        cells=self.fixture()[:3]+[cell('10',2,0,0,60),cell('20',2,1,60,130),cell('30',2,2,130,200)]
        self.assertEqual(annual_header_hints(cells)['hint_count'],0)
